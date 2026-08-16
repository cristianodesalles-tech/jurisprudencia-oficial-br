#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.core import Candidate, CaseProfile, LegalReview, finalize_validation, plan_research, validate_candidate
from engine.network import datajud_search, probe_sources, stj_open_data_search
from engine.domain import SearchRequest
from engine.runtime import build_runtime

TOOLS = [
    {"name":"plan_research","description":"Decompõe um caso e cria plano hierárquico de pesquisa.","inputSchema":{"type":"object","properties":{"case":{"type":"object"}},"required":["case"]}},
    {"name":"validate_candidate","description":"Valida metadados e hash de inteiro teor oficial; nunca valida sem arquivo.","inputSchema":{"type":"object","properties":{"candidate":{"type":"object"},"document_path":{"type":"string"}},"required":["candidate","document_path"]}},
    {"name":"finalize_legal_validation","description":"Promove CONFIRMADO a VALIDADO após seis checagens jurídicas humanas explícitas.","inputSchema":{"type":"object","properties":{"structural":{"type":"object"},"review":{"type":"object"}},"required":["structural","review"]}},
    {"name":"probe_official_sources","description":"Verifica saúde das fontes oficiais configuradas.","inputSchema":{"type":"object","properties":{}}},
    {"name":"search_datajud_metadata","description":"Pesquisa metadados no DataJud; não valida jurisprudência.","inputSchema":{"type":"object","properties":{"court":{"type":"string"},"query":{"type":"object"}},"required":["court","query"]}},
    {"name":"search_stj_open_data","description":"Descobre conjuntos oficiais no portal de dados abertos do STJ.","inputSchema":{"type":"object","properties":{"term":{"type":"string"},"rows":{"type":"integer"}},"required":["term"]}},
    {"name":"search_local_corpus","description":"Pesquisa o acervo próprio por busca lexical e vetorial com ranking jurídico.","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"courts":{"type":"array","items":{"type":"string"}},"branch":{"type":"string"},"state":{"type":"string"},"limit":{"type":"integer"}},"required":["query"]}},
    {"name":"corpus_health","description":"Retorna contagens e integridade da trilha de auditoria do acervo próprio.","inputSchema":{"type":"object","properties":{}}}
]

_runtime = None


def local_runtime():
    global _runtime
    if _runtime is None:
        _runtime = build_runtime()
    return _runtime


def result(value):
    return {"content":[{"type":"text","text":json.dumps(value, ensure_ascii=False, indent=2)}]}


def dispatch(name, args):
    if name == "plan_research": return plan_research(CaseProfile(**args["case"]))
    if name == "validate_candidate": return validate_candidate(Candidate(**args["candidate"]), args["document_path"])
    if name == "finalize_legal_validation": return finalize_validation(args["structural"], LegalReview(**args["review"]))
    if name == "probe_official_sources": return probe_sources(ROOT / "config" / "sources.json")
    if name == "search_datajud_metadata": return datajud_search(args["court"], args["query"])
    if name == "search_stj_open_data": return stj_open_data_search(args["term"], args.get("rows", 20))
    if name == "search_local_corpus":
        hits = local_runtime().search.search(SearchRequest(**args))
        return [{"document_id":hit.document.id,"court":hit.document.court,"case_number":hit.document.case_number,
                 "status":hit.document.status.value,"source_url":hit.document.provenance.source_url,
                 "sha256":hit.document.provenance.content_sha256,"excerpt":hit.chunk.text[:1200],
                 "score":hit.final_score,"reasons":hit.reasons} for hit in hits]
    if name == "corpus_health":
        verification = local_runtime().audit.verify()
        return {"counts":local_runtime().repository.counts(),"audit_chain_valid":verification.valid,
                "audit_events":verification.events}
    raise ValueError(f"ferramenta desconhecida: {name}")


def main():
    for line in sys.stdin:
        try:
            message = json.loads(line)
            method = message.get("method")
            if method == "initialize":
                payload = {"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"jurisprudencia-oficial-br","version":"0.2.0"}}
            elif method == "tools/list": payload = {"tools": TOOLS}
            elif method == "tools/call": payload = result(dispatch(message["params"]["name"], message["params"].get("arguments", {})))
            elif method == "notifications/initialized": continue
            else: raise ValueError(f"método não suportado: {method}")
            print(json.dumps({"jsonrpc":"2.0","id":message.get("id"),"result":payload}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"jsonrpc":"2.0","id":locals().get("message",{}).get("id"),"error":{"code":-32000,"message":str(exc)}}, ensure_ascii=False), flush=True)


if __name__ == "__main__": main()
