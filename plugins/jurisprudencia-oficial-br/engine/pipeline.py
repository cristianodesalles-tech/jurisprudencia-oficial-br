from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .audit import HashChainAudit
from .domain import EvidenceStatus, JudicialDocument, SourceRole, chunk_document
from .embeddings import Embedder
from .repository import Repository
from .storage import ObjectStore


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    inserted: bool
    chunks: int
    raw_key: str
    sha256: str
    status: EvidenceStatus


class IngestionPipeline:
    def __init__(self, repository: Repository, object_store: ObjectStore, embedder: Embedder,
                 audit: HashChainAudit | None = None):
        self.repository = repository
        self.object_store = object_store
        self.embedder = embedder
        self.audit = audit

    def ingest(self, document: JudicialDocument, raw_content: bytes, suffix: str = ".bin") -> IngestionResult:
        document.canonicalize()
        raw_key, digest = self.object_store.put_immutable(raw_content, document.provenance.content_type, suffix)
        if digest != document.provenance.content_sha256:
            raise ValueError("hash declarado diverge do conteúdo bruto")
        if document.provenance.role == SourceRole.VALIDATION:
            document.status = EvidenceStatus.CONFIRMADO
        document.metadata = {**document.metadata, "raw_object_key": raw_key}
        chunks = chunk_document(document)
        vectors = self.embedder.embed([chunk.text for chunk in chunks])
        embedded = [replace(chunk, embedding=tuple(vector)) for chunk, vector in zip(chunks, vectors)]
        inserted = self.repository.upsert_document(document, embedded)
        result = IngestionResult(document.id, inserted, len(embedded), raw_key, digest, document.status)
        if self.audit:
            self.audit.append("document_ingested", {
                "document_id": document.id, "source_id": document.provenance.source_id,
                "source_url": document.provenance.source_url, "sha256": digest,
                "inserted": inserted, "chunks": len(embedded), "status": document.status.value,
            })
        return result
