from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Protocol, Sequence

from .domain import normalize_text


class Embedder(Protocol):
    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Embedding determinístico para testes e operação degradada, sem alegar semântica neural."""

    def __init__(self, dimensions: int = 768):
        if dimensions < 8:
            raise ValueError("dimensions deve ser >= 8")
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[\w§ºª.-]+", normalize_text(text).lower(), flags=re.UNICODE)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("instale o extra production para embeddings neurais") from exc
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
        self._model = SentenceTransformer(self.model_name)
        self.dimensions = int(self._model.get_sentence_embedding_dimension())
        if self.dimensions != 768:
            raise ValueError("o esquema de produção exige embeddings com 768 dimensões")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        prepared = [f"passage: {normalize_text(text)}" for text in texts]
        values = self._model.encode(prepared, normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, row)) for row in values]


def build_embedder() -> Embedder:
    provider = os.getenv("EMBEDDING_PROVIDER", "hashing").lower()
    if provider == "sentence-transformers":
        return SentenceTransformerEmbedder()
    if provider != "hashing":
        raise ValueError(f"EMBEDDING_PROVIDER desconhecido: {provider}")
    return HashingEmbedder()


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vetores com dimensões incompatíveis")
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)
