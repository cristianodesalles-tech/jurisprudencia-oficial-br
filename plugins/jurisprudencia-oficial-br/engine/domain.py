from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


class EvidenceStatus(str, Enum):
    PISTA = "PISTA"
    LOCALIZADO = "LOCALIZADO"
    CONFIRMADO = "CONFIRMADO"
    VALIDADO = "VALIDADO"
    REJEITADO = "REJEITADO"
    NAO_VALIDADO = "NÃO VALIDADO"


class SourceRole(str, Enum):
    DISCOVERY = "discovery"
    VALIDATION = "validation"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def stable_hash(value: bytes | str) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Provenance:
    source_id: str
    source_url: str
    retrieved_at: str
    content_sha256: str
    role: SourceRole
    http_status: int = 200
    content_type: str = "application/octet-stream"
    final_url: str = ""


@dataclass
class JudicialDocument:
    court: str
    case_number: str
    document_type: str
    title: str
    full_text: str
    provenance: Provenance
    panel: str = ""
    rapporteur: str = ""
    judgment_date: str = ""
    publication_date: str = ""
    state: str = ""
    branch: str = ""
    outcome: str = ""
    precedent_kind: str = "ordinary"
    binding: bool = False
    themes: list[str] = field(default_factory=list)
    statutes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    status: EvidenceStatus = EvidenceStatus.LOCALIZADO

    def canonicalize(self) -> "JudicialDocument":
        self.court = normalize_text(self.court).upper()
        self.case_number = normalize_text(self.case_number)
        self.document_type = normalize_text(self.document_type).lower()
        self.title = normalize_text(self.title)
        self.full_text = normalize_text(self.full_text)
        self.panel = normalize_text(self.panel)
        self.rapporteur = normalize_text(self.rapporteur)
        self.state = normalize_text(self.state).upper()
        self.branch = normalize_text(self.branch).lower()
        self.outcome = normalize_text(self.outcome)
        self.precedent_kind = normalize_text(self.precedent_kind).lower() or "ordinary"
        self.themes = sorted(set(filter(None, map(normalize_text, self.themes))))
        self.statutes = sorted(set(filter(None, map(normalize_text, self.statutes))))
        if not self.id:
            self.id = stable_hash(f"{self.court}|{self.case_number}|{self.provenance.content_sha256}")[:32]
        return self

    def fingerprint(self) -> str:
        normalized = {
            "court": self.court,
            "case_number": self.case_number,
            "document_type": self.document_type,
            "full_text": self.full_text,
        }
        return stable_hash(json.dumps(normalized, ensure_ascii=False, sort_keys=True))


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    document_id: str
    ordinal: int
    text: str
    text_sha256: str
    embedding: tuple[float, ...] = ()


@dataclass
class SearchRequest:
    query: str
    courts: list[str] = field(default_factory=list)
    branch: str = ""
    state: str = ""
    date_from: str = ""
    date_to: str = ""
    limit: int = 10
    include_unvalidated: bool = True
    require_local_and_superior: bool = True

    def normalize(self) -> "SearchRequest":
        self.query = normalize_text(self.query)
        self.courts = [normalize_text(court).upper() for court in self.courts]
        self.branch = normalize_text(self.branch).lower()
        self.state = normalize_text(self.state).upper()
        self.limit = min(max(int(self.limit), 1), 100)
        if not self.query:
            raise ValueError("query não pode ser vazia")
        return self


@dataclass
class SearchHit:
    document: JudicialDocument
    chunk: DocumentChunk
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    fusion_score: float = 0.0
    authority_score: float = 0.0
    final_score: float = 0.0
    reasons: list[str] = field(default_factory=list)


def chunk_document(document: JudicialDocument, max_chars: int = 2200, overlap: int = 250) -> list[DocumentChunk]:
    if max_chars < 200 or overlap < 0 or overlap >= max_chars:
        raise ValueError("parâmetros de chunk inválidos")
    text = document.full_text
    if not text:
        return []
    chunks: list[DocumentChunk] = []
    start = 0
    ordinal = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if boundary > start + max_chars // 2:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            digest = stable_hash(piece)
            chunks.append(DocumentChunk(
                id=stable_hash(f"{document.id}|{ordinal}|{digest}")[:32],
                document_id=document.id,
                ordinal=ordinal,
                text=piece,
                text_sha256=digest,
            ))
            ordinal += 1
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def to_dict(value: Any) -> dict[str, Any]:
    payload = asdict(value)
    for key, item in list(payload.items()):
        if isinstance(item, Enum):
            payload[key] = item.value
    return payload
