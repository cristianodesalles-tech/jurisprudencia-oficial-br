from __future__ import annotations

import re
from dataclasses import dataclass

from .audit import HashChainAudit
from .domain import EvidenceStatus, utcnow
from .evidence import EvidenceRuleViolation, assert_promotable
from .repository import Repository

OAB_PATTERN = re.compile(r"^[A-Z]{2}\s*\d{2,7}$")
NON_HUMAN_REVIEWERS = {
    "agente", "assistente", "bot", "claude", "chatgpt", "gpt", "ia", "ai",
    "sistema", "automatico", "automático", "auto", "robo", "robô", "llm", "modelo",
}


class ReviewerNotIdentified(ValueError):
    pass


@dataclass
class ValidationChecklist:
    reviewer: str
    reviewer_oab: str
    document_sha256: str
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

    def assert_human_reviewer(self) -> None:
        name = (self.reviewer or "").strip()
        if len(name.split()) < 2:
            raise ReviewerNotIdentified("informe o nome completo do advogado revisor")
        if any(token.lower() in NON_HUMAN_REVIEWERS for token in name.split()):
            raise ReviewerNotIdentified("o revisor do selo VALIDADO precisa ser uma pessoa, não o próprio agente")
        oab = (self.reviewer_oab or "").strip().upper().replace("/", "").replace(".", "")
        if not OAB_PATTERN.match(oab):
            raise ReviewerNotIdentified("informe a inscrição OAB do revisor no formato UF 00000")


class LegalValidationService:
    def __init__(self, repository: Repository, audit: HashChainAudit | None = None):
        self.repository, self.audit = repository, audit

    def review(self, document_id: str, checklist: ValidationChecklist) -> dict:
        document = self.repository.get_document(document_id)
        if document is None:
            raise KeyError(document_id)
        checklist.assert_human_reviewer()
        assert_promotable(document, (checklist.document_sha256 or "").strip().lower())
        checks = checklist.checks()
        missing = [name for name, value in checks.items() if not value]
        status = EvidenceStatus.VALIDADO if not missing else EvidenceStatus.NAO_VALIDADO
        record = {
            "reviewer": checklist.reviewer.strip(),
            "reviewer_oab": checklist.reviewer_oab.strip(),
            "document_sha256": checklist.document_sha256.strip().lower(),
            "reviewed_at": utcnow(),
            "checklist": {**checks,
                          "reviewer_oab": checklist.reviewer_oab.strip(),
                          "document_sha256": checklist.document_sha256.strip().lower()},
            "notes": checklist.notes,
            "missing": missing,
        }
        self.repository.save_legal_review(document_id, record, status)
        if self.audit:
            self.audit.append("legal_review", {
                "document_id": document_id, "result": status.value,
                "reviewer": record["reviewer"], "reviewer_oab": record["reviewer_oab"],
                "document_sha256": record["document_sha256"], "missing": missing,
            })
        return {"document_id": document_id, "status": status.value, **record}
