from __future__ import annotations

import json
import os
try:
    import fcntl
except ImportError:  # pragma: no cover - Windows local fallback; produção usa Linux/Docker
    fcntl = None
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .domain import stable_hash, utcnow


GENESIS_HASH = "0" * 64
_LOCAL_LOCK = threading.RLock()


@dataclass(frozen=True)
class AuditVerification:
    valid: bool
    events: int
    error_index: int | None = None
    message: str = ""


class HashChainAudit:
    """Log JSONL encadeado; detecta alteração ou remoção no meio da sequência."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cached_hash: str | None = None

    def append(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with _LOCAL_LOCK, lock_path.open("a", encoding="utf-8") as lock:
            if fcntl:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            previous = self.last_hash()
            body = {"at": utcnow(), "event": event, "payload": payload, "previous_hash": previous}
            body["event_hash"] = stable_hash(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._cached_hash = body["event_hash"]
            if fcntl:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            return body

    def events(self) -> Iterable[dict[str, Any]]:
        if not self.path.exists():
            return []
        parsed = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parsed.append(json.loads(line))
        return parsed

    def last_hash(self) -> str:
        """Lê apenas a última linha. Reler o arquivo inteiro a cada gravação é quadrático."""
        if self._cached_hash is not None:
            return self._cached_hash
        if not self.path.exists() or self.path.stat().st_size == 0:
            return GENESIS_HASH
        with self.path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            window = min(size, 65536)
            stream.seek(size - window)
            tail = stream.read(window).decode("utf-8", errors="replace").splitlines()
        for line in reversed(tail):
            if line.strip():
                self._cached_hash = json.loads(line)["event_hash"]
                return self._cached_hash
        return GENESIS_HASH

    def verify(self) -> AuditVerification:
        previous = GENESIS_HASH
        total = 0
        for index, item in enumerate(self.events()):
            total = index + 1
            if item.get("previous_hash") != previous:
                return AuditVerification(False, index, index, "encadeamento anterior divergente")
            claimed = item.get("event_hash", "")
            body = {key: value for key, value in item.items() if key != "event_hash"}
            actual = stable_hash(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            if claimed != actual:
                return AuditVerification(False, index + 1, index, "hash do evento divergente")
            previous = claimed
        return AuditVerification(True, total)
