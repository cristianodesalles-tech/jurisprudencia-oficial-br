#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "jurisprudencia-oficial-br"
sys.path.insert(0, str(PLUGIN))
from engine.connectors import SourceRegistry
from engine.embeddings import HashingEmbedder
from engine.repository import SQLiteRepository


def main() -> int:
    checks = []
    checks.append(("python>=3.11", sys.version_info >= (3, 11), sys.version.split()[0]))
    for binary in ("docker", "git"):
        checks.append((binary, shutil.which(binary) is not None, shutil.which(binary) or "não encontrado"))
    try:
        registry = SourceRegistry(PLUGIN / "config" / "sources.json")
        checks.append(("source-registry", len(registry.sources) >= 7, f"{len(registry.sources)} fontes"))
    except Exception as exc:
        checks.append(("source-registry", False, str(exc)))
    try:
        repository = SQLiteRepository(":memory:")
        checks.append(("sqlite", repository.counts() == {"documents": 0, "chunks": 0}, "operacional"))
        checks.append(("embedding-fallback", len(HashingEmbedder().embed(["teste"])[0]) == 768, "768 dimensões"))
    except Exception as exc:
        checks.append(("core", False, str(exc)))
    for name, passed, detail in checks:
        print(f"{'OK' if passed else 'FALHA'}\t{name}\t{detail}")
    required = {"python>=3.11", "source-registry", "sqlite", "embedding-fallback"}
    return 0 if all(passed for name, passed, _ in checks if name in required) else 1


if __name__ == "__main__": raise SystemExit(main())
