from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPERIOR_COURTS = {"STF", "STJ", "TST", "TSE", "STM"}
ACCOUNTING_COURTS = {"TCU", "TCE-SP", "TCE-PE", "TCE-RJ"}

# Tipos que são referência abstrata: valem por si, não narram um caso concreto.
# Ficam em faixa própria para não disputarem o top-k com acórdãos longos.
ABSTRACT_REFERENCE_TYPES = {
    "sumula", "sumula_stj", "sumula_vinculante", "enunciado", "oj", "ojt", "pn",
    "tema_repetitivo_stj", "tema_tnu", "tema_irr", "tema_iac", "tema_irdr",
}

BINDING_STRONG = {"sumula_vinculante"}
QUALIFIED_PRECEDENT = {"tema_repetitivo_stj", "tema_tnu", "tema_irr", "tema_iac", "tema_irdr",
                       "repercussao_geral", "repetitivo"}
CUPOLA_PANELS = ("plenário", "plenario", "corte especial", "órgão especial", "orgao especial",
                 "pleno", "seção", "secao", "sdi-1", "sdi-2", "sbdi-1", "sbdi-2")
CONCENTRATED_CLASSES = ("ADI", "ADC", "ADPF", "ADO")
MONOCRATIC_TYPES = {"monocratica", "monocratica_sv", "decisao"}
CONSULTATIVE_TYPES = {"informativo", "parecer", "nota_tecnica", "parecer-previo",
                      "resposta-consulta", "jursel"}


@dataclass(frozen=True)
class AuthorityVerdict:
    level: str
    binding: bool
    collegiate: bool
    abstract_reference: bool
    reasons: tuple[str, ...]


@lru_cache(maxsize=1)
def ranking_config(path: str | None = None) -> dict[str, Any]:
    target = Path(path) if path else Path(__file__).resolve().parents[1] / "config" / "ranking.json"
    return json.loads(target.read_text(encoding="utf-8"))


def _is_concentrated(case_number: str, document_type: str) -> bool:
    head = (case_number or "").strip().upper()
    return any(head.startswith(item) for item in CONCENTRATED_CLASSES) and document_type != "monocratica"


def classify(court: str, document_type: str, panel: str = "", case_number: str = "",
             precedent_kind: str = "", trusted: bool = False) -> AuthorityVerdict:
    """Deriva o nível de autoridade do que o documento é.

    `precedent_kind` é alegação de quem importou (por exemplo, "este acórdão julgou um
    tema repetitivo"). Ela só levanta o nível quando `trusted` é verdadeiro, isto é,
    quando o documento já foi conferido na fonte oficial. Lote não compra autoridade.
    """
    court = (court or "").strip().upper()
    document_type = (document_type or "acordao").strip().lower()
    panel_normalized = (panel or "").strip().lower()
    reasons: list[str] = [f"tipo:{document_type}"]
    abstract = document_type in ABSTRACT_REFERENCE_TYPES
    monocratic = document_type in MONOCRATIC_TYPES
    collegiate = not monocratic
    cupola = any(marker in panel_normalized for marker in CUPOLA_PANELS)
    claimed = (precedent_kind or "").strip().lower()
    if trusted and claimed:
        if claimed in BINDING_STRONG:
            return AuthorityVerdict("A", True, collegiate, abstract, tuple(reasons + ["sumula-vinculante-conferida"]))
        if claimed in QUALIFIED_PRECEDENT:
            return AuthorityVerdict("B", True, collegiate, abstract,
                                    tuple(reasons + [f"precedente-qualificado-conferido:{claimed}"]))

    if document_type in BINDING_STRONG:
        return AuthorityVerdict("A", True, True, abstract, tuple(reasons + ["sumula-vinculante"]))
    if document_type in {"sumula", "sumula_stj"} and court in {"STF", "STJ", "TST", "TSE"}:
        return AuthorityVerdict("A", True, True, abstract, tuple(reasons + ["sumula-de-tribunal-superior"]))
    if _is_concentrated(case_number, document_type) and court == "STF":
        return AuthorityVerdict("A", True, True, abstract, tuple(reasons + ["controle-concentrado"]))
    if document_type in QUALIFIED_PRECEDENT:
        return AuthorityVerdict("B", True, True, abstract, tuple(reasons + ["precedente-qualificado"]))
    if document_type in {"oj", "ojt", "pn"}:
        return AuthorityVerdict("C", False, True, abstract, tuple(reasons + ["orientacao-de-orgao-de-cupula"]))
    if court in ACCOUNTING_COURTS or document_type in CONSULTATIVE_TYPES:
        return AuthorityVerdict("E", False, collegiate, abstract, tuple(reasons + ["consulta"]))
    if cupola and collegiate:
        return AuthorityVerdict("C", False, True, abstract, tuple(reasons + ["orgao-de-cupula"]))
    return AuthorityVerdict("D", False, collegiate, abstract, tuple(reasons + ["orientativo"]))


CASE_PATTERNS = (
    re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"),
    re.compile(r"\b\d{20}\b"),
    re.compile(r"\b(?:REsp|AREsp|RE|ARE|HC|RHC|MS|AI|AgInt|EDcl|RR|AIRR|ED|ADI|ADC|ADPF)\s*n?º?\s*[\d.\-/]{4,}", re.I),
)


def normalize_case_number(value: str) -> str:
    return re.sub(r"[^0-9a-z]", "", (value or "").lower())


def extract_case_references(query: str) -> list[str]:
    """Números e classes citados literalmente na consulta, para fixação exata."""
    found: list[str] = []
    for pattern in CASE_PATTERNS:
        found.extend(match.group(0) for match in pattern.finditer(query or ""))
    return list(dict.fromkeys(found))
