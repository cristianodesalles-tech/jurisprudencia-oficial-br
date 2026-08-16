from __future__ import annotations

import math
from datetime import date
from typing import Iterable, Sequence

from .domain import EvidenceStatus, SearchHit, SearchRequest
from .embeddings import Embedder
from .repository import Repository


SUPERIOR_COURTS = {"STF", "STJ", "TST", "TSE", "STM"}
QUALIFIED = {
    "sumula_vinculante": 1.00, "controle_concentrado": 1.00,
    "repercussao_geral": 0.95, "repetitivo": 0.95,
    "irdr": 0.90, "iac": 0.90, "sumula": 0.82, "ordinary": 0.50,
}


def rrf_score(rank: int | None, constant: int = 60) -> float:
    return 0.0 if rank is None else 1.0 / (constant + rank)


def authority_score(hit: SearchHit, target_state: str = "") -> tuple[float, list[str]]:
    document = hit.document
    score = QUALIFIED.get(document.precedent_kind, 0.45)
    reasons = [f"autoridade:{document.precedent_kind}"]
    if document.binding:
        score += 0.35
        reasons.append("vinculante")
    if document.court in SUPERIOR_COURTS:
        score += 0.18
        reasons.append("tribunal-superior")
    if target_state and document.court == f"TJ{target_state}":
        score += 0.16
        reasons.append("tribunal-local")
    if target_state == "GO" and document.court == "TRT18":
        score += 0.16
        reasons.append("tribunal-regional")
    if document.status == EvidenceStatus.VALIDADO:
        score += 0.20
        reasons.append("validado")
    elif document.status == EvidenceStatus.CONFIRMADO:
        score += 0.08
        reasons.append("confirmado")
    try:
        year = int((document.judgment_date or document.publication_date)[:4])
        age = max(date.today().year - year, 0)
        score += 0.12 * math.exp(-age / 8)
        reasons.append("atualidade")
    except (ValueError, TypeError):
        reasons.append("data-ausente")
    return score, reasons


class HybridSearchEngine:
    def __init__(self, repository: Repository, embedder: Embedder, rrf_constant: int = 60):
        self.repository = repository
        self.embedder = embedder
        self.rrf_constant = rrf_constant

    def search(self, request: SearchRequest) -> list[SearchHit]:
        request.normalize()
        filters = {"branch": request.branch, "state": request.state,
                   "date_from": request.date_from, "date_to": request.date_to}
        if len(request.courts) == 1:
            filters["court"] = request.courts[0]
        window = max(request.limit * 5, 30)
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
        results = []
        for hit in merged.values():
            hit.fusion_score = rrf_score(hit.lexical_rank, self.rrf_constant) + rrf_score(hit.semantic_rank, self.rrf_constant)
            hit.authority_score, hit.reasons = authority_score(hit, request.state)
            hit.final_score = hit.fusion_score * (1.0 + hit.authority_score)
            if not request.include_unvalidated and hit.document.status not in {EvidenceStatus.CONFIRMADO, EvidenceStatus.VALIDADO}:
                continue
            if request.courts and hit.document.court not in request.courts:
                continue
            results.append(hit)
        results.sort(key=lambda item: (-item.final_score, item.document.id, item.chunk.ordinal))
        deduped = self._best_chunk_per_document(results)
        if request.require_local_and_superior:
            deduped = self._diversify(deduped, request.state)
        return deduped[:request.limit]

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
