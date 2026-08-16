from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, TypeVar

from .domain import utcnow


T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class SourceCircuit:
    source_id: str
    failure_threshold: int = 3
    failures: int = 0
    state: CircuitState = CircuitState.CLOSED
    last_failure: str = ""
    updated_at: str = field(default_factory=utcnow)

    def success(self) -> None:
        self.failures, self.state, self.last_failure, self.updated_at = 0, CircuitState.CLOSED, "", utcnow()

    def failure(self, reason: str, access_control: bool = False) -> None:
        self.failures += 1
        self.last_failure, self.updated_at = reason, utcnow()
        if access_control or self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def allow(self) -> bool:
        return self.state != CircuitState.OPEN

    def manual_half_open(self) -> None:
        self.state, self.updated_at = CircuitState.HALF_OPEN, utcnow()


class ResilientExecutor(Generic[T]):
    def __init__(self, circuit: SourceCircuit, attempts: int = 3):
        self.circuit, self.attempts = circuit, max(1, attempts)

    def run(self, operation: Callable[[], T], transient: tuple[type[Exception], ...]) -> T:
        if not self.circuit.allow():
            raise RuntimeError(f"circuito aberto para {self.circuit.source_id}")
        last: Exception | None = None
        for _ in range(self.attempts):
            try:
                value = operation()
                self.circuit.success()
                return value
            except transient as exc:
                last = exc
        self.circuit.failure(str(last))
        raise last if last else RuntimeError("operação falhou")
