from __future__ import annotations

from engine.domain import JudicialDocument, Provenance, SourceRole, stable_hash, utcnow
from engine.evidence import EvidenceGrader


class StubRegistry:
    """Registro de teste: isola a lógica do motor do modo de acesso real de cada portal.

    No registro de produção TJGO, TRT18 e STF estão como `assisted` e não validam por
    busca automatizada. Os testes de pipeline e de revisão tratam da regra, não do portal.
    """

    def __init__(self, validating=("tjgo-juris", "stj-scon", "tst-juris", "trf1-cjf", "stf-juris", "trt18-hub")):
        self.validating = set(validating)

    def get(self, source_id: str) -> dict:
        if source_id not in self.validating:
            raise KeyError(source_id)
        return {"id": source_id, "validation_capability": True}


def test_grader() -> EvidenceGrader:
    return EvidenceGrader(StubRegistry())

# Fontes registradas em config/sources.json com validation_capability true.
SOURCE_BY_COURT = {
    "TJGO": "tjgo-juris", "STJ": "stj-scon", "STF": "stf-juris",
    "TST": "tst-juris", "TRT18": "trt18-hub",
}
FILLER = "Vistos, relatados e discutidos estes autos, acordam os integrantes do órgão colegiado. "


def make_document(*, court: str = "TJGO", case_number: str = "5000000-00.2025.8.09.0001",
                  text: str = "O mero inadimplemento contratual não gera dano moral automaticamente.",
                  source_role: SourceRole = SourceRole.VALIDATION, precedent_kind: str = "ordinary",
                  binding: bool = False, judgment_date: str = "2025-03-01",
                  source_id: str | None = None, pad: bool = False) -> tuple[JudicialDocument, bytes]:
    body = text + (" " + FILLER * 20 if pad else "")
    raw = body.encode("utf-8")
    provenance = Provenance(
        source_id=source_id or SOURCE_BY_COURT.get(court, f"{court.lower()}-test"),
        source_url=f"https://consulta.{court.lower()}.jus.br/documento/1",
        retrieved_at=utcnow(), content_sha256=stable_hash(raw), role=source_role,
        content_type="text/plain", final_url=f"https://consulta.{court.lower()}.jus.br/documento/1",
    )
    document = JudicialDocument(
        court=court, case_number=case_number, document_type="acordao", title="Acórdão de teste",
        full_text=body, provenance=provenance, panel="1ª Câmara", rapporteur="Relator de teste",
        judgment_date=judgment_date, publication_date=judgment_date, state="GO", branch="civil",
        outcome="recurso desprovido", precedent_kind=precedent_kind, binding=binding,
    )
    return document, raw


def make_confirmable_document(**kwargs) -> tuple[JudicialDocument, bytes]:
    """Documento com as três provas: fonte que valida, resposta HTTP oficial e inteiro teor."""
    kwargs.setdefault("pad", True)
    return make_document(**kwargs)
