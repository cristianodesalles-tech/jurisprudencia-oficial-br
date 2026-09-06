from __future__ import annotations

import math
from datetime import date
from typing import Any, Sequence

from .authority import (SUPERIOR_COURTS, classify, extract_case_references,
                        normalize_case_number, ranking_config)
from .domain import EvidenceStatus, SearchHit, SearchRequest
from .embeddings import Embedder
from .repository import Repository


def rrf_score(rank: int | None, constant: int = 60) -> float:
    return 0.0 if rank is None else 1.0 / (constant + rank)


def authority_score(hit: SearchHit, target_state: str = "", config: dict[str, Any] | None = None) -> tuple[float, list[str]]:
    """Pontua autoridade a partir da classificação derivada, não de campo declarado."""
    settings = (config or ranking_config())["autoridade"]
    document = hit.document
    trusted = document.status in {EvidenceStatus.CONFIRMADO, EvidenceStatus.VALIDADO}
    verdict = classify(document.court, document.document_type, document.panel, document.case_number,
                       document.precedent_kind, trusted)
    hit.authority_level = verdict.level
    hit.abstract_reference = verdict.abstract_reference
    reasons = [f"autoridade:{verdict.level}", *verdict.reasons]
    score = settings["bonus_nivel"].get(verdict.level, 0.0)
    if verdict.binding:
        reasons.append("vinculante")
        if verdict.collegiate:
            score += settings["bonus_colegiado_vinculante"]
            reasons.append("colegiado-vinculante")
    if not verdict.collegiate:
        penalty = (settings["penalidade_monocratica_com_sumula"]
                   if document.document_type == "monocratica_sv" else settings["penalidade_monocratica"])
        score -= penalty
        reasons.append("monocratica")
    score += settings["ajuste_por_tipo"].get(document.document_type, 0.0)
    if document.court in SUPERIOR_COURTS:
        score += settings["bonus_tribunal_superior"]
        reasons.append("tribunal-superior")
    if target_state and document.court in {f"TJ{target_state}", f"TRF{target_state}"}:
        score += settings["bonus_tribunal_local"]
        reasons.append("tribunal-local")
    if document.status == EvidenceStatus.VALIDADO:
        score += 0.20
        reasons.append("validado")
    elif document.status == EvidenceStatus.CONFIRMADO:
        score += 0.08
        reasons.append("confirmado")
    return score * settings["peso"], reasons


def recency_score(hit: SearchHit, config: dict[str, Any]) -> tuple[float, str]:
    settings = config["recencia"]
    if hit.semantic_score < settings["portao_semantico_minimo"]:
        return 0.0, "recencia-nao-pontua-sem-aderencia"
    document = hit.document
    try:
        year = int((document.judgment_date or document.publication_date)[:4])
    except (ValueError, TypeError):
        return settings["score_data_desconhecida"], "data-ausente"
    age = max(date.today().year - year, 0)
    raw = settings["peso"] * math.exp(-age * math.log(2) / settings["meia_vida_anos"])
    return min(raw, settings["contribuicao_maxima"]), "atualidade"


def procedural_penalty(hit: SearchHit, config: dict[str, Any]) -> tuple[float, str | None]:
    settings = config["processual"]
    haystack = f"{hit.document.title} {hit.chunk.text}".lower()
    if any(marker in haystack for marker in settings["marcadores"]):
        return settings["peso_penalidade"], "discute-processo-nao-a-tese"
    return 0.0, None


class HybridSearchEngine:
    def __init__(self, repository: Repository, embedder: Embedder, rrf_constant: int | None = None,
                 config: dict[str, Any] | None = None):
        self.repository = repository
        self.embedder = embedder
        self.config = config or ranking_config()
        self.rrf_constant = rrf_constant or self.config["fusao"]["rrf_k"]

    def search(self, request: SearchRequest) -> list[SearchHit]:
        request.normalize()
        cortes = self.config["cortes"]
        filters = {"branch": request.branch, "state": request.state,
                   "date_from": request.date_from, "date_to": request.date_to}
        if len(request.courts) == 1:
            filters["court"] = request.courts[0]
        window = max(request.limit * 5, cortes["topk_hibrido"])
        lexical = self.repository.search_lexical(request.query, window, filters)
        query_embedding = self.embedder.embed([f"query: {request.query}"])[0]
        semantic = self.repository.search_semantic(query_embedding, window, filters)

        merged: dict[str, SearchHit] = {}
        for rank, (document, chunk, score) in enumerate(lexical, 1):
            hit = merged.setdefault(chunk.id, SearchHit(document=document, chunk=chunk))
            hit.lexical_rank, hit.lexical_score = rank, score
        for rank, (document, chunk, score) in enumerate(semantic, 1):
            hit = merged.setdefault(chunk.id, SearchHit(document=document, chunk=chunk))
            hit.semantic_rank, hit.semantic_score = rank, score

        citations = [normalize_case_number(item) for item in extract_case_references(request.query)]
        results: list[SearchHit] = []
        for hit in merged.values():
            if not request.include_overruled and hit.document.metadata.get("overruling_status") == "superado":
                continue
            if not request.include_unvalidated and hit.document.status not in {
                    EvidenceStatus.CONFIRMADO, EvidenceStatus.VALIDADO}:
                continue
            if request.courts and hit.document.court not in request.courts:
                continue
            if request.tipos and hit.document.document_type not in request.tipos:
                continue
            hit.fusion_score = (rrf_score(hit.lexical_rank, self.rrf_constant)
                                + rrf_score(hit.semantic_rank, self.rrf_constant))
            hit.authority_score, hit.reasons = authority_score(hit, request.state, self.config)
            hit.recency_score, recency_reason = recency_score(hit, self.config)
            hit.reasons.append(recency_reason)
            hit.procedural_penalty, procedural_reason = procedural_penalty(hit, self.config)
            if procedural_reason:
                hit.reasons.append(procedural_reason)
            normalized = normalize_case_number(hit.document.case_number)
            hit.pinned = bool(normalized and any(ref and (ref in normalized or normalized in ref) for ref in citations))
            if hit.pinned:
                hit.reasons.append("numero-citado-na-consulta")
            hit.final_score = (hit.fusion_score * (1.0 + hit.authority_score - hit.procedural_penalty)
                               + hit.recency_score * hit.fusion_score)
            if hit.semantic_score and hit.semantic_score < cortes["piso_relevancia"] and not hit.pinned:
                continue
            results.append(hit)

        results.sort(key=lambda item: (not item.pinned, -item.final_score, item.document.id, item.chunk.ordinal))
        deduped = self._best_chunk_per_document(results)
        pedido_explicito = bool(request.tipos)
        principal = [hit for hit in deduped if pedido_explicito or not hit.abstract_reference]
        referencias = [] if pedido_explicito else [hit for hit in deduped if hit.abstract_reference]
        if request.require_local_and_superior:
            principal = self._diversify(principal, request.state)
        limite = min(request.limit, cortes["topk_final"]) if request.limit > cortes["topk_final"] else request.limit
        return principal[:limite] + referencias[:cortes["maximo_referencias_abstratas"]]

    @staticmethod
    def _best_chunk_per_document(hits: Sequence[SearchHit]) -> list[SearchHit]:
        seen, output = set(), []
        for hit in hits:
            if hit.document.id not in seen:
                seen.add(hit.document.id)
                output.append(hit)
        return output

    @staticmethod
    def _diversify(hits: list[SearchHit], state: str) -> list[SearchHit]:
        local = {f"TJ{state}"} if state else set()
        if state == "GO":
            local.add("TRT18")
        first_local = next((hit for hit in hits if hit.document.court in local), None)
        first_superior = next((hit for hit in hits if hit.document.court in SUPERIOR_COURTS), None)
        prefix = [hit for hit in (first_local, first_superior) if hit is not None]
        ids = {hit.document.id for hit in prefix}
        return prefix + [hit for hit in hits if hit.document.id not in ids]
