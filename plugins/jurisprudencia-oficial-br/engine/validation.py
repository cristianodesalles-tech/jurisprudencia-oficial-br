from __future__ import annotations

from dataclasses import asdict, dataclass

from .audit import HashChainAudit
from .domain import EvidenceStatus, utcnow
from .repository import Repository


@dataclass
class ValidationChecklist:
    reviewer: str
    excerpt_verified: bool
    majority_reasoning_verified: bool
    factual_fit_verified: bool
    current_law_verified: bool
    adverse_authority_searched: bool
    metadata_crosschecked: bool
    notes: str = ""

    def checks(self) -> dict[str, bool]:
        return {
            "excerpt_verified": self.excerpt_verified,
            "majority_reasoning_verified": self.majority_reasoning_verified,
            "factual_fit_verified": self.factual_fit_verified,
            "current_law_verified": self.current_law_verified,
            "adverse_authority_searched": self.adverse_authority_searched,
            "metadata_crosschecked": self.metadata_crosschecked,
        }


class LegalValidationService:
    def __init__(self, repository: Repository, audit: HashChainAudit | None = None):
        self.repository, self.audit = repository, audit

    def review(self, document_id: str, checklist: ValidationChecklist) -> dict:
        document = self.repository.get_document(document_id)
        if document is None:
            raise KeyError(document_id)
        if document.status not in {EvidenceStatus.CONFIRMADO, EvidenceStatus.VALIDADO, EvidenceStatus.NAO_VALIDADO}:
            raise ValueError("somente documento CONFIRMADO pode ser submetido à validação jurídica")
        checks = checklist.checks()
        missing = [name for name, value in checks.items() if not value]
        if not checklist.reviewer.strip():
            missing.append("reviewer")
        status = EvidenceStatus.VALIDADO if not missing else EvidenceStatus.NAO_VALIDADO
        record = {
            "reviewer": checklist.reviewer.strip(), "reviewed_at": utcnow(),
            "checklist": checks, "notes": checklist.notes, "missing": missing,
        }
        self.repository.save_legal_review(document_id, record, status)
        if self.audit:
            self.audit.append("legal_review", {"document_id": document_id, "result": status.value,
                                                "reviewer": record["reviewer"], "missing": missing})
        return {"document_id": document_id, "status": status.value, **record}
