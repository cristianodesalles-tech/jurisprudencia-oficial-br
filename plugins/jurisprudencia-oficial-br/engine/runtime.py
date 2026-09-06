from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .audit import HashChainAudit
from .embeddings import Embedder, build_embedder
from .pipeline import IngestionPipeline
from .repository import PostgresRepository, Repository, SQLiteRepository
from .search import HybridSearchEngine
from .storage import FileObjectStore, ObjectStore, S3ObjectStore


@dataclass
class Runtime:
    repository: Repository
    object_store: ObjectStore
    embedder: Embedder
    pipeline: IngestionPipeline
    search: HybridSearchEngine
    audit: HashChainAudit


def default_state_dir() -> Path:
    """Diretório de estado estável, independente do diretório de trabalho do cliente.

    A pasta do plugin é sincronizada e pode ser reescrita a cada atualização, por isso
    o acervo mora no espaço de dados do usuário e não dentro do pacote.
    """
    override = os.getenv("STATE_DIR", "").strip()
    if override and not override.startswith("${"):
        return Path(override).expanduser()
    base = os.getenv("XDG_DATA_HOME", "").strip() or str(Path.home() / ".local" / "share")
    return Path(base).expanduser() / "jurisprudencia-oficial-br"


def build_runtime() -> Runtime:
    state_root = default_state_dir().resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    backend = os.getenv("STORAGE_BACKEND", "sqlite").lower()
    if backend == "postgres":
        repository: Repository = PostgresRepository()
        object_store = S3ObjectStore()
        if os.getenv("AUTO_MIGRATE", "0") == "1":
            repository.migrate()
            object_store.ensure_bucket()
    elif backend == "sqlite":
        repository = SQLiteRepository(state_root / "jurisprudencia.sqlite3")
        object_store = FileObjectStore(state_root / "objects")
    else:
        raise ValueError(f"STORAGE_BACKEND inválido: {backend}")
    embedder = build_embedder()
    audit = HashChainAudit(state_root / "audit" / "events.jsonl")
    pipeline = IngestionPipeline(repository, object_store, embedder, audit)
    return Runtime(repository, object_store, embedder, pipeline, HybridSearchEngine(repository, embedder), audit)
