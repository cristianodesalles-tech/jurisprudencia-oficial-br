from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Iterable

from .domain import JudicialDocument, Provenance, SourceRole, stable_hash, utcnow
from .pipeline import IngestionPipeline, IngestionResult
from .connectors import validate_official_url


class UnsafeArchive(ValueError):
    pass


def safe_zip_members(content: bytes, *, max_files: int = 5000, max_uncompressed: int = 2_000_000_000,
                     max_ratio: int = 200) -> Iterable[tuple[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > max_files:
            raise UnsafeArchive("arquivo contém itens demais")
        total = sum(info.file_size for info in infos)
        if total > max_uncompressed:
            raise UnsafeArchive("conteúdo descompactado excede o limite")
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or info.is_dir():
                if info.is_dir():
                    continue
                raise UnsafeArchive("caminho inseguro no ZIP")
            if info.file_size and info.compress_size and info.file_size / info.compress_size > max_ratio:
                raise UnsafeArchive("razão de compressão suspeita")
            yield info.filename, archive.read(info)


def parse_records(name: str, content: bytes) -> Iterable[dict[str, Any]]:
    lower = name.lower()
    text = content.decode("utf-8-sig", errors="strict")
    if lower.endswith((".jsonl", ".ndjson")):
        for line in text.splitlines():
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    yield item
        return
    if lower.endswith(".json"):
        payload = json.loads(text)
        items = payload if isinstance(payload, list) else payload.get("records", payload.get("results", []))
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if isinstance(item, dict):
                yield item
        return
    if lower.endswith(".csv"):
        yield from csv.DictReader(io.StringIO(text))
        return
    raise ValueError(f"formato de lote não suportado: {name}")


@dataclass
class RecordMapping:
    source_id: str
    source_url: str
    default_court: str
    role: SourceRole = SourceRole.DISCOVERY
    aliases: dict[str, list[str]] = field(default_factory=lambda: {
        "case_number": ["case_number", "numeroProcesso", "numero_processo", "processo"],
        "full_text": ["full_text", "inteiroTeor", "inteiro_teor", "texto", "ementa"],
        "title": ["title", "titulo", "ementa"], "court": ["court", "tribunal"],
        "panel": ["panel", "orgaoJulgador", "orgao_julgador"],
        "rapporteur": ["rapporteur", "relator", "ministroRelator"],
        "judgment_date": ["judgment_date", "dataJulgamento", "data_julgamento"],
        "publication_date": ["publication_date", "dataPublicacao", "data_publicacao"],
        "outcome": ["outcome", "decisao", "resultado"],
    })

    def __post_init__(self) -> None:
        validate_official_url(self.source_url, resolve_dns=False)

    def value(self, record: dict[str, Any], field_name: str, default: str = "") -> str:
        for alias in self.aliases.get(field_name, [field_name]):
            value = record.get(alias)
            if value is not None and str(value).strip():
                return str(value)
        return default

    def document(self, record: dict[str, Any], index: int) -> tuple[JudicialDocument, bytes]:
        raw = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        case_number = self.value(record, "case_number")
        full_text = self.value(record, "full_text")
        if not case_number or len(full_text) < 40:
            raise ValueError("registro sem número ou texto suficiente")
        provenance = Provenance(
            source_id=self.source_id, source_url=f"{self.source_url}#record={index}", retrieved_at=utcnow(),
            content_sha256=stable_hash(raw), role=self.role, content_type="application/json",
            final_url=self.source_url,
        )
        known_aliases = {alias for aliases in self.aliases.values() for alias in aliases}
        metadata = {key: value for key, value in record.items() if key not in known_aliases}
        return JudicialDocument(
            court=self.value(record, "court", self.default_court), case_number=case_number,
            document_type=str(record.get("document_type", "acordao")),
            title=self.value(record, "title", f"Documento {case_number}"), full_text=full_text,
            provenance=provenance, panel=self.value(record, "panel"), rapporteur=self.value(record, "rapporteur"),
            judgment_date=self.value(record, "judgment_date"), publication_date=self.value(record, "publication_date"),
            state=str(record.get("state", "")), branch=str(record.get("branch", "")),
            outcome=self.value(record, "outcome"), precedent_kind=str(record.get("precedent_kind", "ordinary")),
            binding=bool(record.get("binding", False)), metadata=metadata,
        ), raw


class BulkImporter:
    def __init__(self, pipeline: IngestionPipeline, mapping: RecordMapping):
        self.pipeline, self.mapping = pipeline, mapping

    def import_file(self, name: str, content: bytes) -> dict[str, Any]:
        files = list(safe_zip_members(content)) if name.lower().endswith(".zip") else [(name, content)]
        inserted, duplicates, rejected, results = 0, 0, [], []
        index = 0
        for member_name, member in files:
            if not member_name.lower().endswith((".json", ".jsonl", ".ndjson", ".csv")):
                continue
            for record in parse_records(member_name, member):
                try:
                    document, raw = self.mapping.document(record, index)
                    result = self.pipeline.ingest(document, raw, ".json")
                    inserted += int(result.inserted); duplicates += int(not result.inserted)
                    results.append(result.document_id)
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    rejected.append({"index": index, "reason": str(exc)})
                index += 1
        return {"processed": index, "inserted": inserted, "duplicates": duplicates,
                "rejected": rejected, "document_ids": results}
