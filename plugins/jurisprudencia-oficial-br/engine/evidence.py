from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .connectors import SourceRegistry
from .domain import EvidenceStatus, JudicialDocument, SourceRole, is_official_url, stable_hash

MIN_FULL_TEXT_CHARS = 1500
MIN_EMENTA_CHARS = 40


class EvidenceRuleViolation(ValueError):
    """Erro de integridade: tentativa de gravar evidência acima do grau provado."""


@dataclass(frozen=True)
class EvidenceDecision:
    status: EvidenceStatus
    reasons: list[str] = field(default_factory=list)
    full_text_present: bool = False
    fetch_proved: bool = False
    source_can_validate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reasons": list(self.reasons),
            "full_text_present": self.full_text_present,
            "fetch_proved": self.fetch_proved,
            "source_can_validate": self.source_can_validate,
        }


def default_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "sources.json"


class EvidenceGrader:
    """Decide o grau de evidência a partir de prova, nunca de declaração do chamador.

    Regra dura: CONFIRMADO exige as três provas simultâneas.
      1. a fonte está registrada em config/sources.json com validation_capability true;
      2. existe prova de busca real (HTTP 200 em URL final de domínio oficial);
      3. o texto guardado é inteiro teor, não ementa nem resumo.
    Faltando qualquer uma, o documento para em LOCALIZADO (URL oficial) ou PISTA.
    """

    def __init__(self, registry: SourceRegistry | None = None):
        if registry is None:
            try:
                registry = SourceRegistry(default_registry_path())
            except (OSError, ValueError, KeyError):
                registry = None
        self.registry = registry

    def _source_can_validate(self, source_id: str, document: JudicialDocument) -> tuple[bool, str]:
        if self.registry is None:
            return False, "registro-de-fontes-indisponivel"
        try:
            source = self.registry.get(source_id)
        except KeyError:
            return False, "fonte-nao-registrada"
        if source.get("validation_capability"):
            return True, "fonte-valida-por-busca-automatizada"
        if source.get("access_mode") == "assisted":
            # Portal com proteção que não contornamos. A conferência vale quando uma
            # pessoa identificada abriu a página oficial e registrou o que viu.
            metadata = document.metadata or {}
            if metadata.get("capture_mode") == "assisted" and str(metadata.get("capture_operator_oab") or "").strip():
                return True, "fonte-assistida-com-captura-humana-identificada"
            return False, "fonte-assistida-exige-captura-humana-identificada"
        return False, "fonte-sem-capacidade-de-validacao-no-registro"

    @staticmethod
    def _fetch_proved(document: JudicialDocument, raw_content: bytes) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        provenance = document.provenance
        if provenance.role != SourceRole.VALIDATION:
            reasons.append("papel-da-fonte-nao-e-validacao")
        if provenance.http_status != 200:
            reasons.append(f"sem-http-200 ({provenance.http_status})")
        final_url = provenance.final_url or ""
        if not final_url:
            reasons.append("sem-url-final-de-resposta")
        elif not is_official_url(final_url):
            reasons.append("url-final-fora-de-dominio-oficial")
        if not is_official_url(provenance.source_url):
            reasons.append("url-de-origem-fora-de-dominio-oficial")
        if not raw_content:
            reasons.append("sem-conteudo-bruto")
        elif stable_hash(raw_content) != provenance.content_sha256:
            reasons.append("hash-declarado-diverge-do-bruto")
        return (not reasons), reasons

    @staticmethod
    def _full_text_present(document: JudicialDocument) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if document.metadata.get("ementa_only"):
            reasons.append("registro-marcado-como-ementa")
        text = document.full_text or ""
        if len(text) < MIN_FULL_TEXT_CHARS:
            reasons.append(f"texto-curto-demais-para-inteiro-teor ({len(text)} caracteres)")
        ementa = (document.ementa or "").strip()
        if ementa and text.strip() == ementa:
            reasons.append("texto-identico-a-ementa")
        return (not reasons), reasons

    def grade(self, document: JudicialDocument, raw_content: bytes = b"") -> EvidenceDecision:
        can_validate, source_reason = self._source_can_validate(document.provenance.source_id, document)
        fetched, fetch_reasons = self._fetch_proved(document, raw_content)
        has_text, text_reasons = self._full_text_present(document)
        reasons = list(fetch_reasons) + list(text_reasons)
        if not can_validate:
            reasons.insert(0, source_reason)
        if can_validate and fetched and has_text:
            return EvidenceDecision(EvidenceStatus.CONFIRMADO, ["prova-completa", source_reason], True, True, True)
        status = EvidenceStatus.LOCALIZADO if is_official_url(document.provenance.source_url) else EvidenceStatus.PISTA
        return EvidenceDecision(status, reasons, has_text, fetched, can_validate)


def assert_promotable(document: JudicialDocument, document_sha256: str) -> None:
    """Guarda de promoção jurídica: só CONFIRMADO com hash conferido pode virar VALIDADO."""
    if document.status != EvidenceStatus.CONFIRMADO:
        raise EvidenceRuleViolation(
            f"somente documento CONFIRMADO pode ser promovido; estado atual: {document.status.value}"
        )
    if not document_sha256 or document_sha256 != document.provenance.content_sha256:
        raise EvidenceRuleViolation("hash conferido pelo revisor não corresponde ao documento armazenado")
