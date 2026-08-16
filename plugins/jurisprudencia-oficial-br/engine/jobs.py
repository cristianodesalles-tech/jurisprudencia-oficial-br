from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Protocol


class JobQueue(Protocol):
    def enqueue(self, function: str, payload: dict[str, Any]) -> str: ...


@dataclass
class InlineQueue:
    handlers: dict[str, Callable[[dict[str, Any]], Any]]

    def enqueue(self, function: str, payload: dict[str, Any]) -> str:
        if function not in self.handlers:
            raise KeyError(function)
        self.handlers[function](payload)
        return "inline-complete"


class RedisQueue:
    def __init__(self):
        try:
            from redis import Redis
            from rq import Queue, Retry
        except ImportError as exc:
            raise RuntimeError("instale redis e rq para filas de produção") from exc
        connection = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        self.queue = Queue("ingestion", connection=connection, default_timeout=600)
        self.retry = Retry(max=3, interval=[10, 30, 120])

    def enqueue(self, function: str, payload: dict[str, Any]) -> str:
        job = self.queue.enqueue(function, payload, retry=self.retry)
        return job.id
