from __future__ import annotations

from .connectors import OfficialHttpConnector
from .domain import JudicialDocument, SourceRole
from .runtime import build_runtime


def ingest_url(payload: dict) -> dict:
    role = SourceRole(payload.pop("role", "validation"))
    source_id = payload.pop("source_id")
    url = payload.pop("url")
    fetched = OfficialHttpConnector(source_id, role).fetch(url)
    document = JudicialDocument(full_text=fetched.text, provenance=fetched.provenance, **payload)
    result = build_runtime().pipeline.ingest(document, fetched.content, fetched.suffix)
    return {
        "document_id": result.document_id, "inserted": result.inserted, "chunks": result.chunks,
        "sha256": result.sha256, "status": result.status.value,
    }
