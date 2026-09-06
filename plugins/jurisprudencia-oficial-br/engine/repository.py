from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Protocol, Sequence

from .domain import DocumentChunk, EvidenceStatus, JudicialDocument, Provenance, SourceRole
from .embeddings import cosine_similarity

SUPERIOR_COURTS = ("STF", "STJ", "TST", "TSE", "STM")
_SUPERIOR_SQL = ",".join(f"'{court}'" for court in SUPERIOR_COURTS)


class Repository(Protocol):
    def migrate(self) -> None: ...
    def upsert_document(self, document: JudicialDocument, chunks: Sequence[DocumentChunk]) -> bool: ...
    def get_document(self, document_id: str) -> JudicialDocument | None: ...
    def search_lexical(self, query: str, limit: int, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk, float]]: ...
    def search_semantic(self, embedding: Sequence[float], limit: int, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk, float]]: ...
    def counts(self) -> dict[str, int]: ...
    def get_chunks(self, document_id: str) -> list[DocumentChunk]: ...
    def save_legal_review(self, document_id: str, review: dict, status: EvidenceStatus) -> None: ...


def _document_to_record(document: JudicialDocument) -> dict:
    return {
        "id": document.id, "court": document.court, "case_number": document.case_number,
        "document_type": document.document_type, "title": document.title, "full_text": document.full_text,
        "panel": document.panel, "rapporteur": document.rapporteur, "judgment_date": document.judgment_date,
        "publication_date": document.publication_date, "state": document.state, "branch": document.branch,
        "outcome": document.outcome, "ementa": document.ementa, "precedent_kind": document.precedent_kind,
        "binding": int(document.binding), "themes": json.dumps(document.themes, ensure_ascii=False),
        "statutes": json.dumps(document.statutes, ensure_ascii=False),
        "metadata": json.dumps(document.metadata, ensure_ascii=False, sort_keys=True),
        "status": document.status.value, "source_id": document.provenance.source_id,
        "source_url": document.provenance.source_url, "retrieved_at": document.provenance.retrieved_at,
        "content_sha256": document.provenance.content_sha256, "source_role": document.provenance.role.value,
        "http_status": document.provenance.http_status, "content_type": document.provenance.content_type,
        "final_url": document.provenance.final_url, "fingerprint": document.fingerprint(),
    }


def _row_to_document(row: sqlite3.Row | dict) -> JudicialDocument:
    item = dict(row)
    def decoded(value, default):
        if value is None:
            return default
        return json.loads(value) if isinstance(value, str) else value
    provenance = Provenance(
        source_id=item["source_id"], source_url=item["source_url"], retrieved_at=item["retrieved_at"],
        content_sha256=item["content_sha256"], role=SourceRole(item["source_role"]),
        http_status=item["http_status"], content_type=item["content_type"], final_url=item["final_url"],
    )
    return JudicialDocument(
        id=item["id"], court=item["court"], case_number=item["case_number"],
        document_type=item["document_type"], title=item["title"], full_text=item["full_text"],
        panel=item["panel"], rapporteur=item["rapporteur"], judgment_date=item["judgment_date"],
        publication_date=item["publication_date"], state=item["state"], branch=item["branch"],
        outcome=item["outcome"], ementa=item.get("ementa", "") or "", precedent_kind=item["precedent_kind"], binding=bool(item["binding"]),
        themes=decoded(item["themes"], []), statutes=decoded(item["statutes"], []),
        metadata=decoded(item["metadata"], {}), status=EvidenceStatus(item["status"]), provenance=provenance,
    )


class SQLiteRepository:
    """Adapter operacional e de testes; preserva os mesmos invariantes do PostgreSQL."""

    def __init__(self, path: str | Path = ":memory:"):
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self) -> None:
        self.connection.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY, court TEXT NOT NULL, case_number TEXT NOT NULL,
          document_type TEXT NOT NULL, title TEXT NOT NULL, full_text TEXT NOT NULL,
          panel TEXT NOT NULL, rapporteur TEXT NOT NULL, judgment_date TEXT NOT NULL,
          publication_date TEXT NOT NULL, state TEXT NOT NULL, branch TEXT NOT NULL,
          outcome TEXT NOT NULL, ementa TEXT NOT NULL DEFAULT '', precedent_kind TEXT NOT NULL, binding INTEGER NOT NULL,
          themes TEXT NOT NULL, statutes TEXT NOT NULL, metadata TEXT NOT NULL, status TEXT NOT NULL,
          source_id TEXT NOT NULL, source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
          content_sha256 TEXT NOT NULL, source_role TEXT NOT NULL, http_status INTEGER NOT NULL,
          content_type TEXT NOT NULL, final_url TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          ordinal INTEGER NOT NULL, text TEXT NOT NULL, text_sha256 TEXT NOT NULL,
          embedding TEXT NOT NULL, UNIQUE(document_id, ordinal)
        );
        CREATE INDEX IF NOT EXISTS idx_documents_court ON documents(court);
        CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_number);
        CREATE INDEX IF NOT EXISTS idx_documents_dates ON documents(judgment_date, publication_date);
        CREATE TABLE IF NOT EXISTS legal_reviews (
          id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL REFERENCES documents(id),
          reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, checklist TEXT NOT NULL,
          notes TEXT NOT NULL, resulting_status TEXT NOT NULL
        );
        """)
        self._fts = self._ensure_fts()
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(documents)")}
        if "ementa" not in columns:
            self.connection.execute("ALTER TABLE documents ADD COLUMN ementa TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    def _ensure_fts(self) -> bool:
        """Índice de texto do próprio SQLite. Sem ele a busca lexical varre o acervo inteiro."""
        try:
            self.connection.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='rowid');
            CREATE TRIGGER IF NOT EXISTS chunks_fts_ins AFTER INSERT ON chunks BEGIN
              INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_fts_del AFTER DELETE ON chunks BEGIN
              INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
            END;
            """)
            self.connection.commit()
            return True
        except sqlite3.OperationalError:
            return False

    def get_chunks(self, document_id: str) -> list[DocumentChunk]:
        rows = self.connection.execute(
            "SELECT id, document_id, ordinal, text, text_sha256 FROM chunks WHERE document_id=? ORDER BY ordinal",
            (document_id,)).fetchall()
        return [DocumentChunk(row["id"], row["document_id"], row["ordinal"], row["text"], row["text_sha256"])
                for row in rows]

    def upsert_document(self, document: JudicialDocument, chunks: Sequence[DocumentChunk]) -> bool:
        record = _document_to_record(document)
        existing = self.connection.execute("SELECT id FROM documents WHERE fingerprint = ?", (record["fingerprint"],)).fetchone()
        if existing:
            return False
        columns = list(record)
        placeholders = ",".join("?" for _ in columns)
        with self.connection:
            self.connection.execute(
                f"INSERT INTO documents ({','.join(columns)}) VALUES ({placeholders})",
                tuple(record[column] for column in columns),
            )
            self.connection.executemany(
                "INSERT INTO chunks (id, document_id, ordinal, text, text_sha256, embedding) VALUES (?,?,?,?,?,?)",
                [(chunk.id, chunk.document_id, chunk.ordinal, chunk.text, chunk.text_sha256,
                  json.dumps(chunk.embedding)) for chunk in chunks],
            )
        return True

    def get_document(self, document_id: str) -> JudicialDocument | None:
        row = self.connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return _row_to_document(row) if row else None

    def _sql_filters(self, filters: dict[str, str]) -> tuple[str, list[str]]:
        clauses, values = self._filter_clauses(filters)
        return ((" AND " + " AND ".join(clauses)) if clauses else ""), values

    @staticmethod
    def _filter_clauses(filters: dict[str, str]) -> tuple[list[str], list[str]]:
        clauses, values = [], []
        for key in ("court", "branch"):
            if filters.get(key):
                clauses.append(f"d.{key} = ?")
                values.append(filters[key])
        if filters.get("state"):
            clauses.append(f"(d.state = ? OR d.court IN ({_SUPERIOR_SQL}))")
            values.append(filters["state"])
        if filters.get("date_from"):
            clauses.append("COALESCE(NULLIF(d.judgment_date,''), d.publication_date) >= ?")
            values.append(filters["date_from"])
        if filters.get("date_to"):
            clauses.append("COALESCE(NULLIF(d.judgment_date,''), d.publication_date) <= ?")
            values.append(filters["date_to"])
        return clauses, values

    def _candidate_rows(self, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk]]:
        clauses, values = self._filter_clauses(filters)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            f"SELECT d.*, c.id chunk_id, c.ordinal, c.text chunk_text, c.text_sha256, c.embedding FROM documents d JOIN chunks c ON c.document_id=d.id {where}",
            values,
        ).fetchall()
        return [
            (_row_to_document(row), DocumentChunk(row["chunk_id"], row["id"], row["ordinal"], row["chunk_text"],
                                                   row["text_sha256"], tuple(json.loads(row["embedding"]))))
            for row in rows
        ]

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = [term for term in re.findall(r"[\wÀ-ÿ]{2,}", query or "")]
        return " OR ".join(f'"{term}"' for term in terms)

    def search_lexical(self, query: str, limit: int, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk, float]]:
        if self._fts:
            expression = self._fts_query(query)
            if not expression:
                return []
            where, values = self._sql_filters(filters)
            sql = (f"SELECT d.*, c.id chunk_id, c.ordinal, c.text chunk_text, c.text_sha256, c.embedding, "
                   f"-bm25(chunks_fts) score FROM chunks_fts "
                   f"JOIN chunks c ON c.rowid = chunks_fts.rowid JOIN documents d ON d.id = c.document_id "
                   f"WHERE chunks_fts MATCH ? {where} ORDER BY score DESC LIMIT ?")
            try:
                rows = self.connection.execute(sql, [expression, *values, limit]).fetchall()
            except sqlite3.OperationalError:
                self._fts = False
            else:
                return [(_row_to_document(row),
                         DocumentChunk(row["chunk_id"], row["id"], row["ordinal"], row["chunk_text"],
                                       row["text_sha256"], tuple(json.loads(row["embedding"]))),
                         float(row["score"])) for row in rows]
        return self._search_lexical_scan(query, limit, filters)

    def _search_lexical_scan(self, query: str, limit: int, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk, float]]:
        terms = [term.lower() for term in query.split() if len(term) > 1]
        scored = []
        for document, chunk in self._candidate_rows(filters):
            haystack = f"{document.title} {document.case_number} {chunk.text}".lower()
            score = sum(haystack.count(term) for term in terms) / max(len(terms), 1)
            if score:
                scored.append((document, chunk, float(score)))
        return sorted(scored, key=lambda item: (-item[2], item[0].id, item[1].ordinal))[:limit]

    def search_semantic(self, embedding: Sequence[float], limit: int, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk, float]]:
        scored = [(doc, chunk, cosine_similarity(embedding, chunk.embedding)) for doc, chunk in self._candidate_rows(filters)]
        return sorted(scored, key=lambda item: (-item[2], item[0].id, item[1].ordinal))[:limit]

    def counts(self) -> dict[str, int]:
        documents = self.connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"documents": documents, "chunks": chunks}

    def save_legal_review(self, document_id: str, review: dict, status: EvidenceStatus) -> None:
        with self.connection:
            changed = self.connection.execute("UPDATE documents SET status=? WHERE id=?", (status.value, document_id)).rowcount
            if changed != 1:
                raise KeyError(document_id)
            self.connection.execute(
                "INSERT INTO legal_reviews(document_id,reviewer,reviewed_at,checklist,notes,resulting_status) VALUES (?,?,?,?,?,?)",
                (document_id, review["reviewer"], review["reviewed_at"], json.dumps(review["checklist"], sort_keys=True),
                 review.get("notes", ""), status.value),
            )


class PostgresRepository:
    def __init__(self, dsn: str | None = None):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("instale psycopg[binary] para PostgreSQL") from exc
        self.psycopg = psycopg
        self.dict_row = dict_row
        self.dsn = dsn or os.environ["DATABASE_URL"]

    def _connect(self):
        return self.psycopg.connect(self.dsn, row_factory=self.dict_row)

    def migrate(self) -> None:
        migration = Path(__file__).resolve().parents[1] / "infra" / "migrations" / "001_init.sql"
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(migration.read_text(encoding="utf-8"))

    def upsert_document(self, document: JudicialDocument, chunks: Sequence[DocumentChunk]) -> bool:
        record = _document_to_record(document)
        columns = list(record)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM documents WHERE fingerprint=%s", (record["fingerprint"],))
            if cursor.fetchone():
                return False
            cursor.execute(
                f"INSERT INTO documents ({','.join(columns)}) VALUES ({','.join('%s' for _ in columns)})",
                tuple(record[column] for column in columns),
            )
            cursor.executemany(
                "INSERT INTO chunks (id,document_id,ordinal,text,text_sha256,embedding) VALUES (%s,%s,%s,%s,%s,%s::vector)",
                [(chunk.id, chunk.document_id, chunk.ordinal, chunk.text, chunk.text_sha256,
                  self._vector_literal(chunk.embedding)) for chunk in chunks],
            )
        return True

    def get_document(self, document_id: str) -> JudicialDocument | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM documents WHERE id=%s", (document_id,))
            row = cursor.fetchone()
        return _row_to_document(row) if row else None

    @staticmethod
    def _filters(filters: dict[str, str]) -> tuple[str, list[str]]:
        clauses, values = [], []
        for key in ("court", "branch"):
            if filters.get(key):
                clauses.append(f"d.{key}=%s")
                values.append(filters[key])
        if filters.get("state"):
            clauses.append(f"(d.state=%s OR d.court IN ({_SUPERIOR_SQL}))")
            values.append(filters["state"])
        if filters.get("date_from"):
            clauses.append("COALESCE(NULLIF(d.judgment_date,''),d.publication_date)>=%s")
            values.append(filters["date_from"])
        if filters.get("date_to"):
            clauses.append("COALESCE(NULLIF(d.judgment_date,''),d.publication_date)<=%s")
            values.append(filters["date_to"])
        return ((" AND " + " AND ".join(clauses)) if clauses else "", values)

    @staticmethod
    def _vector_literal(embedding: Sequence[float]) -> str:
        return "[" + ",".join(f"{float(value):.9g}" for value in embedding) + "]"

    def search_lexical(self, query: str, limit: int, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk, float]]:
        extra, values = self._filters(filters)
        sql = f"""SELECT d.*, c.id chunk_id,c.ordinal,c.text chunk_text,c.text_sha256,c.embedding::text,
          ts_rank_cd(c.search_vector, websearch_to_tsquery('portuguese', %s)) score
          FROM chunks c JOIN documents d ON d.id=c.document_id
          WHERE c.search_vector @@ websearch_to_tsquery('portuguese', %s) {extra}
          ORDER BY score DESC LIMIT %s"""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, [query, query, *values, limit])
            rows = cursor.fetchall()
        return [( _row_to_document(row), DocumentChunk(row["chunk_id"], row["id"], row["ordinal"], row["chunk_text"], row["text_sha256"]), float(row["score"]) ) for row in rows]

    def search_semantic(self, embedding: Sequence[float], limit: int, filters: dict[str, str]) -> list[tuple[JudicialDocument, DocumentChunk, float]]:
        extra, values = self._filters(filters)
        sql = f"""SELECT d.*,c.id chunk_id,c.ordinal,c.text chunk_text,c.text_sha256,c.embedding::text,
          1-(c.embedding <=> %s::vector) score FROM chunks c JOIN documents d ON d.id=c.document_id
          WHERE c.embedding IS NOT NULL {extra} ORDER BY c.embedding <=> %s::vector LIMIT %s"""
        vector = self._vector_literal(embedding)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, [vector, *values, vector, limit])
            rows = cursor.fetchall()
        return [( _row_to_document(row), DocumentChunk(row["chunk_id"], row["id"], row["ordinal"], row["chunk_text"], row["text_sha256"]), float(row["score"]) ) for row in rows]

    def get_chunks(self, document_id: str) -> list[DocumentChunk]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id,document_id,ordinal,text,text_sha256 FROM chunks WHERE document_id=%s ORDER BY ordinal",
                           (document_id,))
            rows = cursor.fetchall()
        return [DocumentChunk(row["id"], row["document_id"], row["ordinal"], row["text"], row["text_sha256"])
                for row in rows]

    def counts(self) -> dict[str, int]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT (SELECT count(*) FROM documents) documents,(SELECT count(*) FROM chunks) chunks")
            return dict(cursor.fetchone())

    def save_legal_review(self, document_id: str, review: dict, status: EvidenceStatus) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE documents SET status=%s WHERE id=%s", (status.value, document_id))
            if cursor.rowcount != 1:
                raise KeyError(document_id)
            cursor.execute(
                "INSERT INTO legal_reviews(document_id,reviewer,reviewed_at,checklist,notes,resulting_status) VALUES (%s,%s,%s,%s::jsonb,%s,%s)",
                (document_id, review["reviewer"], review["reviewed_at"], json.dumps(review["checklist"], sort_keys=True),
                 review.get("notes", ""), status.value),
            )
