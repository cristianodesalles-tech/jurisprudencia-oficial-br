from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .core import append_audit, now_iso


class FailureKind(str, Enum):
    TRANSIENT = "transient"
    EMPTY = "empty"
    PORTAL_MOVED = "portal_moved"
    ACCESS_CONTROL = "access_control"
    INVALID_EVIDENCE = "invalid_evidence"


@dataclass
class Attempt:
    source_id: str
    query: str
    strategy: str
    outcome: str
    failure: FailureKind | None = None
    details: str = ""


class StrategyController:
    """Decide fallbacks permitidos sem alterar ou fabricar evidência."""

    def __init__(self, max_attempts: int = 12):
        self.max_attempts = max_attempts
        self.attempts: list[Attempt] = []

    def record(self, attempt: Attempt, audit_path: str | None = None) -> None:
        self.attempts.append(attempt)
        if audit_path:
            append_audit(audit_path, {"event": "search_attempt", "at": now_iso(), **asdict(attempt)})

    def next_action(self) -> dict[str, Any]:
        if not self.attempts:
            return {"action": "start", "strategy": "exact_phrase_with_fact_anchor"}
        if len(self.attempts) >= self.max_attempts:
            return {"action": "stop", "reason": "attempt_budget_exhausted", "negative_report_required": True}
        last = self.attempts[-1]
        if last.outcome == "success":
            return {"action": "validate_full_text"}
        if last.failure == FailureKind.TRANSIENT:
            return {"action": "retry", "backoff_seconds": min(8, 2 ** min(len(self.attempts), 3))}
        if last.failure == FailureKind.EMPTY:
            return {"action": "broaden_query", "strategy": "remove_one_filter_add_synonyms"}
        if last.failure == FailureKind.PORTAL_MOVED:
            return {"action": "resolve_from_official_hub", "update_config_only_after_review": True}
        if last.failure == FailureKind.INVALID_EVIDENCE:
            return {"action": "reject_candidate_and_continue", "preserve_audit": True}
        if last.failure == FailureKind.ACCESS_CONTROL:
            return {"action": "stop", "reason": "do_not_bypass_access_control", "negative_report_required": True}
        return {"action": "continue", "strategy": "search_by_case_number_or_statute"}
