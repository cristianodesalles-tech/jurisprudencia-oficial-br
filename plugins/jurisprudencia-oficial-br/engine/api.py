from __future__ import annotations

import hmac
import os
from functools import lru_cache
from typing import Any

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as exc:
    raise RuntimeError("instale o extra production para executar a API") from exc

from .domain import SearchRequest
from .jobs import RedisQueue
from .metrics import metrics
from .runtime import Runtime, build_runtime


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=4000)
    courts: list[str] = Field(default_factory=list, max_length=30)
    branch: str = Field(default="", max_length=50)
    state: str = Field(default="", max_length=2)
    date_from: str = Field(default="", max_length=10)
    date_to: str = Field(default="", max_length=10)
    limit: int = Field(default=10, ge=1, le=100)
    include_unvalidated: bool = True
    require_local_and_superior: bool = True


class IngestURLBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=12, max_length=3000)
    source_id: str = Field(min_length=2, max_length=100)
    role: str = Field(default="validation", pattern="^(validation|discovery)$")
    court: str = Field(min_length=2, max_length=20)
    case_number: str = Field(min_length=2, max_length=100)
    document_type: str = Field(default="acordao", max_length=50)
    title: str = Field(min_length=2, max_length=500)
    panel: str = Field(default="", max_length=200)
    rapporteur: str = Field(default="", max_length=200)
    judgment_date: str = Field(default="", max_length=10)
    publication_date: str = Field(default="", max_length=10)
    state: str = Field(default="", max_length=2)
    branch: str = Field(default="", max_length=50)
    outcome: str = Field(default="", max_length=1000)
    precedent_kind: str = Field(default="ordinary", max_length=60)
    binding: bool = False
    themes: list[str] = Field(default_factory=list, max_length=100)
    statutes: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def runtime() -> Runtime:
    return build_runtime()


def require_api_key(x_api_key: str = Header(default="")) -> None:
    configured = [item.strip() for item in os.getenv("API_KEYS", "").split(",") if item.strip()]
    if not configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "API_KEYS não configurado")
    if not any(hmac.compare_digest(x_api_key, item) for item in configured):
        metrics.inc("auth_failures_total")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "chave inválida")


app = FastAPI(title="Jurisprudência Oficial BR", version="0.2.0", docs_url=None, redoc_url=None)


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(_: None = Depends(require_api_key)):
    try:
        counts = runtime().repository.counts()
        audit = runtime().audit.verify()
        return {"status": "ready", "counts": counts, "audit_chain_valid": audit.valid}
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"não pronto: {exc}") from exc


@app.get("/metrics")
def prometheus(_: None = Depends(require_api_key)):
    return Response(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@app.post("/v1/search")
def search(body: SearchBody, _: None = Depends(require_api_key)):
    request = SearchRequest(**body.model_dump())
    hits = runtime().search.search(request)
    metrics.inc("search_requests_total")
    return {
        "query": request.query,
        "count": len(hits),
        "results": [{
            "document_id": hit.document.id, "court": hit.document.court,
            "case_number": hit.document.case_number, "panel": hit.document.panel,
            "rapporteur": hit.document.rapporteur, "judgment_date": hit.document.judgment_date,
            "publication_date": hit.document.publication_date, "status": hit.document.status.value,
            "precedent_kind": hit.document.precedent_kind, "binding": hit.document.binding,
            "source_url": hit.document.provenance.source_url, "final_url": hit.document.provenance.final_url,
            "sha256": hit.document.provenance.content_sha256, "excerpt": hit.chunk.text[:1200],
            "score": round(hit.final_score, 8), "reasons": hit.reasons,
        } for hit in hits],
        "warning": "Resultados são insumos. VALIDADO exige revisão jurídica documentada.",
    }


@app.post("/v1/ingestions", status_code=202)
def enqueue_ingestion(body: IngestURLBody, _: None = Depends(require_api_key)):
    job_id = RedisQueue().enqueue("engine.worker_tasks.ingest_url", body.model_dump())
    metrics.inc("ingestion_jobs_total")
    return {"job_id": job_id, "status": "queued"}
