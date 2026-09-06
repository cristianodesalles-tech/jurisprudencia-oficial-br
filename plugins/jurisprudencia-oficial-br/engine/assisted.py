from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .domain import JudicialDocument, Provenance, SourceRole, is_official_url, stable_hash, utcnow
from .validation import OAB_PATTERN, NON_HUMAN_REVIEWERS, ReviewerNotIdentified

CAPTURE_MODE = "assisted"


class AssistedCaptureError(ValueError):
    pass


def assert_operator(name: str, oab: str) -> None:
    clean = (name or "").strip()
    if len(clean.split()) < 2 or any(token.lower() in NON_HUMAN_REVIEWERS for token in clean.split()):
        raise ReviewerNotIdentified("a captura assistida precisa do nome completo de quem conferiu na tela")
    normalized = (oab or "").strip().upper().replace("/", "").replace(".", "")
    if not OAB_PATTERN.match(normalized):
        raise ReviewerNotIdentified("informe a inscrição OAB de quem conduziu a captura, no formato UF 00000")


@dataclass
class AssistedCapture:
    """Conferência humana em portal protegido, com prova do que foi visto.

    Existe porque TJGO, TRT18 e STF estão como fontes assistidas: têm proteção que o
    plugin não contorna. A saída não é rebaixar a regra, é registrar quem abriu a
    página oficial, qual foi a URL exata e qual o hash do conteúdo conferido.
    """

    court: str
    source_id: str
    official_url: str
    captured_text: str
    raw_content: bytes
    operator: str
    operator_oab: str
    case_number: str
    document_type: str = "acordao"
    title: str = ""
    panel: str = ""
    rapporteur: str = ""
    judgment_date: str = ""
    publication_date: str = ""
    state: str = ""
    branch: str = ""
    outcome: str = ""
    ementa: str = ""
    precedent_kind: str = "ordinary"
    content_type: str = "text/html"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        assert_operator(self.operator, self.operator_oab)
        if not is_official_url(self.official_url):
            raise AssistedCaptureError("a URL conferida precisa ser de domínio oficial .jus.br")
        if not self.raw_content:
            raise AssistedCaptureError("captura sem conteúdo bruto não é prova de nada")
        if not self.case_number.strip():
            raise AssistedCaptureError("informe o número do processo conferido na tela")

    def build(self) -> tuple[JudicialDocument, bytes]:
        provenance = Provenance(
            source_id=self.source_id,
            # URL usada verbatim: o sufixo de roteamento dos portais não é decorativo,
            # truncar a URL gera 404 na conferência posterior.
            source_url=self.official_url,
            retrieved_at=utcnow(),
            content_sha256=stable_hash(self.raw_content),
            role=SourceRole.VALIDATION,
            http_status=200,
            content_type=self.content_type,
            final_url=self.official_url,
        )
        document = JudicialDocument(
            court=self.court, case_number=self.case_number, document_type=self.document_type,
            title=self.title or f"Documento {self.case_number}", full_text=self.captured_text,
            provenance=provenance, panel=self.panel, rapporteur=self.rapporteur,
            judgment_date=self.judgment_date, publication_date=self.publication_date,
            state=self.state, branch=self.branch, outcome=self.outcome, ementa=self.ementa,
            precedent_kind=self.precedent_kind,
            metadata={**self.metadata, "capture_mode": CAPTURE_MODE,
                      "capture_operator": self.operator.strip(),
                      "capture_operator_oab": self.operator_oab.strip(),
                      "captured_at": utcnow()},
        )
        return document, self.raw_content
