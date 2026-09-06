#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from engine.core import Candidate, CaseProfile, LegalReview, append_audit, finalize_validation, plan_research, validate_candidate
from engine.network import datajud_search, probe_sources, stj_open_data_search
from engine.bulk import BulkImporter, RecordMapping
from engine.domain import SearchRequest, SourceRole
from engine.runtime import build_runtime
from engine.validation import LegalValidationService, ValidationChecklist
from engine.worker_tasks import ingest_url
from engine.assisted import AssistedCapture
from engine.overruling import OverrulingEntry, OverrulingRegistry


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Planejamento e validação jurisprudencial auditável")
    subs = parser.add_subparsers(dest="command", required=True)
    plan = subs.add_parser("plan"); plan.add_argument("--case", required=True)
    val = subs.add_parser("validate"); val.add_argument("--candidate", required=True); val.add_argument("--document", required=True); val.add_argument("--audit")
    final = subs.add_parser("finalize"); final.add_argument("--structural", required=True); final.add_argument("--review", required=True); final.add_argument("--audit")
    probe = subs.add_parser("probe"); probe.add_argument("--audit")
    dj = subs.add_parser("datajud"); dj.add_argument("--court", required=True); dj.add_argument("--query", required=True)
    stj = subs.add_parser("stj-open-data"); stj.add_argument("term"); stj.add_argument("--rows", type=int, default=20)
    search = subs.add_parser("search"); search.add_argument("query"); search.add_argument("--state", default=""); search.add_argument("--branch", default=""); search.add_argument("--court", action="append", default=[]); search.add_argument("--limit", type=int, default=10)
    health = subs.add_parser("corpus-health")
    ingest = subs.add_parser("ingest-url"); ingest.add_argument("--metadata", required=True)
    bulk = subs.add_parser("bulk-import"); bulk.add_argument("--file", required=True); bulk.add_argument("--source-id", required=True); bulk.add_argument("--source-url", required=True); bulk.add_argument("--court", required=True);
    capture = subs.add_parser("capture-assisted", help="registra conferência humana em portal protegido")
    capture.add_argument("--metadata", required=True, help="JSON com court, source_id, official_url, case_number e demais campos")
    capture.add_argument("--file", required=True, help="arquivo com o conteúdo conferido na tela")
    capture.add_argument("--operator", required=True); capture.add_argument("--oab", required=True)
    doc = subs.add_parser("document"); doc.add_argument("--document-id", required=True)
    chunk = subs.add_parser("chunk"); chunk.add_argument("--document-id", required=True); chunk.add_argument("--ordinal", type=int, default=0)
    ov_add = subs.add_parser("overruling-add"); ov_add.add_argument("--entry", required=True)
    ov_list = subs.add_parser("overruling-list"); ov_list.add_argument("--term", default="")
    review = subs.add_parser("review"); review.add_argument("--document-id", required=True); review.add_argument("--checklist", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        output = plan_research(CaseProfile(**load(args.case)))
    elif args.command == "validate":
        output = validate_candidate(Candidate(**load(args.candidate)), args.document)
        if args.audit:
            append_audit(args.audit, {"event": "candidate_validation", **output})
    elif args.command == "finalize":
        output = finalize_validation(load(args.structural), LegalReview(**load(args.review)))
        if args.audit:
            append_audit(args.audit, {"event": "legal_validation", **output})
    elif args.command == "probe":
        output = probe_sources(PLUGIN_ROOT / "config" / "sources.json", args.audit)
    elif args.command == "datajud":
        output = datajud_search(args.court, load(args.query))
    elif args.command == "stj-open-data":
        output = stj_open_data_search(args.term, args.rows)
    elif args.command == "search":
        hits = build_runtime().search.search(SearchRequest(args.query, courts=args.court, state=args.state, branch=args.branch, limit=args.limit))
        def render(hit):
            return {"document_id":hit.document.id,"court":hit.document.court,"case_number":hit.document.case_number,
                    "document_type":hit.document.document_type,"status":hit.document.status.value,
                    "authority_level":hit.authority_level,"score":hit.final_score,
                    "source_url":hit.document.provenance.source_url,
                    "sha256":hit.document.provenance.content_sha256,
                    "overruling_status":hit.document.metadata.get("overruling_status"),
                    "trecho":hit.chunk.text,"reasons":hit.reasons}
        output = {"acordaos":[render(h) for h in hits if not h.abstract_reference],
                  "referencias_abstratas":[render(h) for h in hits if h.abstract_reference],
                  "aviso":"Somente VALIDADO entra na minuta."}
    elif args.command == "corpus-health":
        runtime = build_runtime(); audit = runtime.audit.verify()
        output = {"counts":runtime.repository.counts(),"audit_chain_valid":audit.valid,"audit_events":audit.events}
    elif args.command == "ingest-url":
        output = ingest_url(load(args.metadata))
    elif args.command == "bulk-import":
        runtime = build_runtime()
        mapping = RecordMapping(args.source_id, args.source_url, args.court, SourceRole.DISCOVERY)
        output = BulkImporter(runtime.pipeline, mapping).import_file(Path(args.file).name, Path(args.file).read_bytes())
        output["aviso"] = "Lote e espelho entram sempre como descoberta. Inteiro teor exige busca individual na fonte oficial."
    elif args.command == "review":
        runtime = build_runtime()
        output = LegalValidationService(runtime.repository, runtime.audit).review(args.document_id, ValidationChecklist(**load(args.checklist)))
    elif args.command == "capture-assisted":
        payload = load(args.metadata)
        conteudo = Path(args.file).read_bytes()
        texto = conteudo.decode("utf-8", errors="replace")
        capture = AssistedCapture(captured_text=texto, raw_content=conteudo,
                                  operator=args.operator, operator_oab=args.oab, **payload)
        document, raw = capture.build()
        outcome = build_runtime().pipeline.ingest(document, raw, ".html")
        output = {"document_id": outcome.document_id, "status": outcome.status.value, "sha256": outcome.sha256,
                  "chunks": outcome.chunks, "motivos": list(outcome.evidence_reasons)}
    elif args.command == "document":
        runtime = build_runtime(); document = runtime.repository.get_document(args.document_id)
        if document is None:
            raise SystemExit(f"documento não encontrado: {args.document_id}")
        output = {"document_id": document.id, "court": document.court, "case_number": document.case_number,
                  "status": document.status.value, "source_url": document.provenance.source_url,
                  "sha256": document.provenance.content_sha256, "ementa": document.ementa,
                  "inteiro_teor": document.full_text,
                  "chunks_total": len(runtime.repository.get_chunks(document.id))}
    elif args.command == "chunk":
        runtime = build_runtime(); chunks = runtime.repository.get_chunks(args.document_id)
        document = runtime.repository.get_document(args.document_id)
        if document is None or not chunks:
            raise SystemExit(f"sem trechos indexados para {args.document_id}")
        if not 0 <= args.ordinal < len(chunks):
            raise SystemExit(f"trecho fora do intervalo 0..{len(chunks) - 1}")
        atual = chunks[args.ordinal]
        output = {"document_id": document.id, "court": document.court, "case_number": document.case_number,
                  "status": document.status.value, "source_url": document.provenance.source_url,
                  "ordinal": atual.ordinal, "chunks_total": len(chunks),
                  "proximo_ordinal": atual.ordinal + 1 if atual.ordinal + 1 < len(chunks) else None,
                  "texto": atual.text}
    elif args.command == "overruling-add":
        registry = OverrulingRegistry()
        output = {"registrado": registry.add(OverrulingEntry(**load(args.entry))).case_number,
                  "total": len(registry.entries)}
    elif args.command == "overruling-list":
        registry = OverrulingRegistry()
        entradas = registry.search(args.term) if args.term else list(registry.entries.values())
        output = {"total": len(entradas), "entradas": [entry.__dict__ for entry in entradas]}
    else:
        raise AssertionError(args.command)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
