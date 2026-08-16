from __future__ import annotations

from engine.domain import JudicialDocument, Provenance, SourceRole, stable_hash, utcnow


def make_document(*, court: str = "TJGO", case_number: str = "5000000-00.2025.8.09.0001",
                  text: str = "O mero inadimplemento contratual não gera dano moral automaticamente.",
                  source_role: SourceRole = SourceRole.VALIDATION, precedent_kind: str = "ordinary",
                  binding: bool = False, judgment_date: str = "2025-03-01") -> tuple[JudicialDocument, bytes]:
    raw = text.encode("utf-8")
    provenance = Provenance(
        source_id=f"{court.lower()}-test", source_url=f"https://consulta.{court.lower()}.jus.br/documento/1",
        retrieved_at=utcnow(), content_sha256=stable_hash(raw), role=source_role,
        content_type="text/plain", final_url=f"https://consulta.{court.lower()}.jus.br/documento/1",
    )
    document = JudicialDocument(
        court=court, case_number=case_number, document_type="acordao", title="Acórdão de teste",
        full_text=text, provenance=provenance, panel="1ª Câmara", rapporteur="Relator de teste",
        judgment_date=judgment_date, publication_date=judgment_date, state="GO", branch="civil",
        outcome="recurso desprovido", precedent_kind=precedent_kind, binding=binding,
    )
    return document, raw
