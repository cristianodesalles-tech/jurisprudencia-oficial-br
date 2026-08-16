from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from .domain import stable_hash


class ObjectStore(Protocol):
    def put_immutable(self, content: bytes, content_type: str, suffix: str = ".bin") -> tuple[str, str]: ...
    def get(self, key: str) -> bytes: ...


class FileObjectStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_immutable(self, content: bytes, content_type: str, suffix: str = ".bin") -> tuple[str, str]:
        digest = stable_hash(content)
        clean_suffix = suffix if suffix.startswith(".") and suffix[1:].isalnum() else ".bin"
        target = (self.root / digest[:2] / f"{digest}{clean_suffix}").resolve()
        if self.root not in target.parents:
            raise ValueError("chave de armazenamento inválida")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if target.read_bytes() != content:
                raise RuntimeError("colisão de hash detectada")
        return str(target.relative_to(self.root)), digest

    def get(self, key: str) -> bytes:
        target = (self.root / key).resolve()
        if self.root not in target.parents or not target.is_file():
            raise FileNotFoundError(key)
        return target.read_bytes()


class S3ObjectStore:
    def __init__(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("instale boto3 para usar S3/MinIO") from exc
        self.bucket = os.getenv("S3_BUCKET", "jurisprudencia-raw")
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
            region_name=os.getenv("S3_REGION", "us-east-1"),
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put_immutable(self, content: bytes, content_type: str, suffix: str = ".bin") -> tuple[str, str]:
        digest = stable_hash(content)
        clean_suffix = suffix if suffix.startswith(".") and suffix[1:].isalnum() else ".bin"
        key = f"sha256/{digest[:2]}/{digest}{clean_suffix}"
        try:
            existing = self.client.head_object(Bucket=self.bucket, Key=key)
            if existing.get("Metadata", {}).get("sha256") != digest:
                raise RuntimeError("objeto existente com metadado de hash divergente")
            return key, digest
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchKey", "NotFound"}:
                raise
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type,
                                   Metadata={"sha256": digest}, IfNoneMatch="*")
        except Exception as exc:
            response = getattr(exc, "response", {})
            if str(response.get("ResponseMetadata", {}).get("HTTPStatusCode", "")) not in {"409", "412"}:
                raise
        return key, digest

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
