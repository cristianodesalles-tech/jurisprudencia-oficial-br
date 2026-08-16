#!/usr/bin/env python3
from __future__ import annotations

import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".env"


def main() -> int:
    if TARGET.exists():
        raise SystemExit(".env já existe; preservado sem alterações")
    values = {
        "POSTGRES_DB": "jurisprudencia", "POSTGRES_USER": "juris",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32), "REDIS_PASSWORD": secrets.token_urlsafe(32),
        "MINIO_ROOT_USER": "juris-minio", "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(32),
        "S3_BUCKET": "jurisprudencia-raw", "API_KEYS": secrets.token_urlsafe(40), "API_PORT": "8080",
        "EMBEDDING_PROVIDER": "sentence-transformers", "EMBEDDING_MODEL": "intfloat/multilingual-e5-base",
        "DATAJUD_API_KEY": "",
    }
    TARGET.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    TARGET.chmod(0o600)
    print(f"Configuração criada em {TARGET}; permissões 0600")
    return 0


if __name__ == "__main__": raise SystemExit(main())
