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
        events = list(self.events())
        return events[-1]["event_hash"] if events else GENESIS_HASH

    def verify(self) -> AuditVerification:
        previous = GENESIS_HASH
        for index, item in enumerate(self.events()):
            if item.get("previous_hash") != previous:
                return AuditVerification(False, index, index, "encadeamento anterior divergente")
            claimed = item.get("event_hash", "")
            body = {key: value for key, value in item.items() if key != "event_hash"}
            actual = stable_hash(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            if claimed != actual:
                return AuditVerification(False, index + 1, index, "hash do evento divergente")
            previous = claimed
        return AuditVerification(True, len(list(self.events())))
