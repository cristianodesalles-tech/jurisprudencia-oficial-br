#!/usr/bin/env python3
"""Servidor MCP do plugin. Fala JSON-RPC por stdin/stdout, uma mensagem por linha."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.assisted import AssistedCapture
from engine.connectors import SourceRegistry, TRF1SearchConnector
from engine.core import Candidate, CaseProfile, LegalReview, finalize_validation, plan_research, validate_candidate
from engine.domain import SearchRequest
from engine.network import datajud_search, probe_sources, stj_open_data_search
from engine.overruling import OverrulingRegistry
from engine.runtime import build_runtime, default_state_dir

PROTOCOL_VERSION = "2024-11-05"
SERVER_VERSION = "0.5.0"
MAX_RESULT_CHARS = 400_000
AVISO = "Somente documentos VALIDADO podem entrar na minuta. Os demais são pista de pesquisa."

TOOLS = [
    {"name": "plan_research", "description": "Decompõe um caso e cria plano hierárquico de pesquisa.",
     "inputSchema": {"type": "object", "properties": {"case": {"type": "object"}}, "required": ["case"]}},
    {"name": "search_local_corpus",
     "description": "Pesquisa o acervo próprio. Devolve o grau de evidência de cada documento e separa referências abstratas (súmulas e temas) dos acórdãos. Nada aqui é citável antes de VALIDADO.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "courts": {"type": "array", "items": {"type": "string"}},
         "branch": {"type": "string"}, "state": {"type": "string"},
         "tipos": {"type": "array", "items": {"type": "string"}},
         "include_overruled": {"type": "boolean"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "get_document",
     "description": "Devolve o documento inteiro, sem truncar. Use quando precisar do fundamento e não só do trecho.",
     "inputSchema": {"type": "object", "properties": {"document_id": {"type": "string"}}, "required": ["document_id"]}},
    {"name": "get_document_chunk",
     "description": "Pagina o inteiro teor por trecho, repetindo os metadados em cada página, para leitura longa sem perder a identificação do julgado.",
     "inputSchema": {"type": "object", "properties": {
         "document_id": {"type": "string"}, "ordinal": {"type": "integer", "minimum": 0}},
         "required": ["document_id"]}},
    {"name": "ingest_assisted_capture",
     "description": "Registra conferência humana feita em portal protegido (TJGO, TRT18, STF). Exige URL oficial verbatim, texto capturado e o operador identificado com nome e OAB.",
     "inputSchema": {"type": "object", "properties": {"capture": {"type": "object"}}, "required": ["capture"]}},
    {"name": "validate_candidate",
     "description": "Valida metadados e hash de inteiro teor oficial; nunca valida sem arquivo.",
     "inputSchema": {"type": "object", "properties": {"candidate": {"type": "object"}, "document_path": {"type": "string"}},
                     "required": ["candidate", "document_path"]}},
    {"name": "finalize_legal_validation",
     "description": "Promove CONFIRMADO a VALIDADO. Exige revisor humano com nome completo e OAB, hash do inteiro teor conferido e as seis checagens jurídicas. O agente não assina por si.",
     "inputSchema": {"type": "object", "properties": {"structural": {"type": "object"}, "review": {"type": "object"}},
                     "required": ["structural", "review"]}},
    {"name": "overruling_lookup",
     "description": "Consulta o registro de superação por processo ou tema, para injetar no resultado o que a busca não trouxe.",
     "inputSchema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]}},
    {"name": "official_source_status",
     "description": "Expõe cobertura, modo automático ou assistido e proteções observadas nas fontes oficiais.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "probe_official_sources", "description": "Verifica saúde das fontes oficiais configuradas.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "search_trf1_official",
     "description": "Pesquisa até 10 acórdãos no formulário oficial CJF/TRF1. Resultados ficam NÃO VALIDADO até conferir o inteiro teor.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                     "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["query"]}},
    {"name": "search_datajud_metadata", "description": "Pesquisa metadados no DataJud; não prova conteúdo de julgado.",
     "inputSchema": {"type": "object", "properties": {"court": {"type": "string"}, "query": {"type": "object"}},
                     "required": ["court", "query"]}},
    {"name": "search_stj_open_data", "description": "Descobre conjuntos oficiais no portal de dados abertos do STJ.",
     "inputSchema": {"type": "object", "properties": {"term": {"type": "string"}, "rows": {"type": "integer"}},
                     "required": ["term"]}},
    {"name": "prepare_assisted_search",
     "description": "Prepara conferência humana em TJGO, STF ou TRT18 sem contornar CAPTCHA ou WAF.",
     "inputSchema": {"type": "object", "properties": {"court": {"type": "string", "enum": ["TJGO", "STF", "TRT18"]},
                     "query": {"type": "string"}}, "required": ["court", "query"]}},
    {"name": "corpus_health", "description": "Contagens, integridade da trilha de auditoria e onde o acervo está gravado.",
     "inputSchema": {"type": "object", "properties": {}}},
]

_runtime = None


class InvalidParams(ValueError):
    pass


def local_runtime():
    global _runtime
    if _runtime is None:
        _runtime = build_runtime()
    return _runtime


def result(value):
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if len(text) > MAX_RESULT_CHARS:
        text = json.dumps({"erro": "resposta grande demais para uma mensagem",
                           "orientacao": "use get_document_chunk para paginar o inteiro teor"},
                          ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}]}


def _document_payload(document, chunks_total: int) -> dict:
    return {"document_id": document.id, "court": document.court, "case_number": document.case_number,
            "document_type": document.document_type, "title": document.title, "panel": document.panel,
            "rapporteur": document.rapporteur, "judgment_date": document.judgment_date,
            "publication_date": document.publication_date, "outcome": document.outcome,
            "status": document.status.value, "source_url": document.provenance.source_url,
            "sha256": document.provenance.content_sha256, "ementa_only": bool(document.metadata.get("ementa_only")),
            "overruling_status": document.metadata.get("overruling_status"),
            "overruling_nota": document.metadata.get("overruling_nota"),
            "capture_mode": document.metadata.get("capture_mode"), "chunks_total": chunks_total}


def dispatch(name, args):
    runtime = None
    if name in {"search_local_corpus", "get_document", "get_document_chunk", "ingest_assisted_capture", "corpus_health"}:
        runtime = local_runtime()

    if name == "plan_research":
        return plan_research(CaseProfile(**args["case"]))
    if name == "search_local_corpus":
        hits = runtime.search.search(SearchRequest(**args))
        def render(hit):
            return {"document_id": hit.document.id, "court": hit.document.court,
                    "case_number": hit.document.case_number, "document_type": hit.document.document_type,
                    "status": hit.document.status.value, "authority_level": hit.authority_level,
                    "source_url": hit.document.provenance.source_url,
                    "sha256": hit.document.provenance.content_sha256,
                    "trecho": hit.chunk.text, "trecho_ordinal": hit.chunk.ordinal,
                    "ementa_only": bool(hit.document.metadata.get("ementa_only")),
                    "overruling_status": hit.document.metadata.get("overruling_status"),
                    "evidence": hit.document.metadata.get("evidence", {}),
                    "score": hit.final_score, "reasons": hit.reasons}
        principais = [render(hit) for hit in hits if not hit.abstract_reference]
        referencias = [render(hit) for hit in hits if hit.abstract_reference]
        citaveis = [item for item in principais + referencias if item["status"] == "VALIDADO"]
        return {"aviso": AVISO, "citaveis": len(citaveis), "acordaos": principais,
                "referencias_abstratas": referencias}
    if name == "get_document":
        document = runtime.repository.get_document(args["document_id"])
        if document is None:
            raise InvalidParams(f"documento não encontrado: {args['document_id']}")
        chunks = runtime.repository.get_chunks(document.id)
        return {**_document_payload(document, len(chunks)), "ementa": document.ementa,
                "inteiro_teor": document.full_text, "aviso": AVISO}
    if name == "get_document_chunk":
        document = runtime.repository.get_document(args["document_id"])
        if document is None:
            raise InvalidParams(f"documento não encontrado: {args['document_id']}")
        chunks = runtime.repository.get_chunks(document.id)
        ordinal = int(args.get("ordinal", 0))
        if not chunks:
            raise InvalidParams("documento sem trechos indexados")
        if ordinal < 0 or ordinal >= len(chunks):
            raise InvalidParams(f"trecho fora do intervalo 0..{len(chunks) - 1}")
        chunk = chunks[ordinal]
        return {**_document_payload(document, len(chunks)), "ordinal": chunk.ordinal,
                "proximo_ordinal": chunk.ordinal + 1 if chunk.ordinal + 1 < len(chunks) else None,
                "texto": chunk.text, "aviso": AVISO}
    if name == "ingest_assisted_capture":
        payload = dict(args["capture"])
        texto = payload.pop("captured_text", "")
        capture = AssistedCapture(captured_text=texto, raw_content=texto.encode("utf-8"), **payload)
        document, raw = capture.build()
        outcome = runtime.pipeline.ingest(document, raw, ".html")
        return {"document_id": outcome.document_id, "status": outcome.status.value,
                "sha256": outcome.sha256, "chunks": outcome.chunks,
                "motivos": list(outcome.evidence_reasons), "aviso": AVISO}
    if name == "validate_candidate":
        return validate_candidate(Candidate(**args["candidate"]), args["document_path"])
    if name == "finalize_legal_validation":
        return finalize_validation(args["structural"], LegalReview(**args["review"]))
    if name == "overruling_lookup":
        registry = OverrulingRegistry()
        entries = registry.search(args["term"])
        return {"total": len(entries), "entradas": [entry.__dict__ for entry in entries],
                "orientacao": "Precedente vindo daqui entra marcado como [INJETADO DO REGISTRY]."}
    if name == "official_source_status":
        registry = SourceRegistry(ROOT / "config" / "sources.json")
        return {"fontes": list(registry.sources.values())}
    if name == "probe_official_sources":
        return probe_sources(ROOT / "config" / "sources.json")
    if name == "search_trf1_official":
        return TRF1SearchConnector().search(args["query"], int(args.get("limit", 10)))
    if name == "search_datajud_metadata":
        return datajud_search(args["court"], args["query"])
    if name == "search_stj_open_data":
        return stj_open_data_search(args["term"], args.get("rows", 20))
    if name == "prepare_assisted_search":
        registry = SourceRegistry(ROOT / "config" / "sources.json")
        fonte = next((item for item in registry.sources.values() if item.get("court") == args["court"]), {})
        return {"court": args["court"], "query": args["query"], "portal": fonte.get("base_url"),
                "modo": fonte.get("access_mode", "assisted"),
                "instrucao": "Abrir o portal, pesquisar o termo, abrir o inteiro teor e registrar a conferência "
                             "com ingest_assisted_capture, copiando a URL exata da barra de endereços.",
                "regra": "Não contornar CAPTCHA, WAF ou limite de acesso."}
    if name == "corpus_health":
        verification = runtime.audit.verify()
        return {"counts": runtime.repository.counts(), "audit_chain_valid": verification.valid,
                "audit_events": verification.events, "state_dir": str(default_state_dir()),
                "overruling_entries": len(OverrulingRegistry().entries)}
    raise InvalidParams(f"ferramenta desconhecida: {name}")


def handle(message: dict) -> dict | None:
    method = message.get("method")
    if method is None or str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        requested = (message.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        return {"protocolVersion": requested, "capabilities": {"tools": {}},
                "serverInfo": {"name": "jurisprudencia-oficial-br", "version": SERVER_VERSION}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "resources/list":
        return {"resources": []}
    if method == "prompts/list":
        return {"prompts": []}
    if method == "tools/call":
        params = message.get("params") or {}
        return result(dispatch(params.get("name"), params.get("arguments") or {}))
    raise LookupError(method)


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        identifier = None
        try:
            message = json.loads(line)
            identifier = message.get("id")
            payload = handle(message)
            if payload is None:
                continue
            print(json.dumps({"jsonrpc": "2.0", "id": identifier, "result": payload}, ensure_ascii=False), flush=True)
        except LookupError as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": identifier,
                              "error": {"code": -32601, "message": f"método não suportado: {exc}"}},
                             ensure_ascii=False), flush=True)
        except (InvalidParams, KeyError, TypeError, ValueError) as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": identifier,
                              "error": {"code": -32602, "message": str(exc)}}, ensure_ascii=False), flush=True)
        except Exception as exc:  # noqa: BLE001 - o servidor não pode morrer por causa de uma chamada
            print(json.dumps({"jsonrpc": "2.0", "id": identifier,
                              "error": {"code": -32000, "message": f"{type(exc).__name__}: {exc}"}},
                             ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
