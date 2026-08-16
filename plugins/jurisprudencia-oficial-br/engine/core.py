from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from .routing import CourtRouter

OFFICIAL_SUFFIXES = (".jus.br", ".cnj.jus.br")
CNJ_PATTERN = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
STATE_NAMES = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAPÁ": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES", "ESPÍRITO SANTO": "ES", "GOIAS": "GO", "GOIÁS": "GO",
    "MARANHAO": "MA", "MARANHÃO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARÁ": "PA", "PARAIBA": "PB", "PARAÍBA": "PB",
    "PARANA": "PR", "PARANÁ": "PR", "PERNAMBUCO": "PE", "PIAUI": "PI", "PIAUÍ": "PI",
    "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS",
    "RONDONIA": "RO", "RONDÔNIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC",
    "SAO PAULO": "SP", "SÃO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_official_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host.endswith(OFFICIAL_SUFFIXES)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class CaseProfile:
    summary: str
    branch: str
    defended_side: str
    state: str = "GO"
    phase: str = "knowledge"
    theses: list[str] = field(default_factory=list)
    statutes: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    court: str
    case_number: str
    official_record_url: str
    full_text_url: str
    panel: str
    rapporteur: str
    judgment_date: str
    publication_date: str = ""
    holding: str = ""
    applicable_excerpt: str = ""
    excerpt_location: str = ""
    thesis: str = ""
    decisive_facts: list[str] = field(default_factory=list)
    distinctions: list[str] = field(default_factory=list)
    outcome: str = ""


@dataclass
class LegalReview:
    reviewer: str
    excerpt_verified: bool
    majority_reasoning_verified: bool
    factual_fit_verified: bool
    current_law_verified: bool
    adverse_authority_searched: bool
    metadata_crosschecked: bool
    notes: str = ""


def hierarchy(branch: str, state: str) -> list[str]:
    normalized = branch.lower().strip()
    raw_state = state.upper().strip()
    state = STATE_NAMES.get(raw_state, raw_state)
    routed = CourtRouter().route(normalized, state)
    return [*routed["local"], *routed["superior"], "STF se houver questão constitucional"]


def query_variants(thesis: str, statutes: list[str], facts: list[str]) -> list[str]:
    anchor = " ".join(facts[:2]).strip()
    law = " ".join(statutes[:2]).strip()
    raw = [
        f'"{thesis.strip()}" {anchor}'.strip(),
        f'"{thesis.strip()}" {law}'.strip(),
        f'{thesis.strip()} {anchor} {law}'.strip(),
        f'{thesis.strip()} (distinção OR superado OR modulação OR afetação)'.strip(),
    ]
    return list(dict.fromkeys(item for item in raw if item))


def plan_research(profile: CaseProfile) -> dict[str, Any]:
    theses = profile.theses or [profile.summary]
    return {
        "generated_at": now_iso(),
        "case": asdict(profile),
        "hierarchy": hierarchy(profile.branch, profile.state),
        "minimum_coverage": {"local_or_regional": 1, "superior": 1, "total": 2},
        "theses": [
            {"thesis": thesis, "queries": query_variants(thesis, profile.statutes, profile.facts)}
            for thesis in theses
        ],
        "mandatory_checks": [
            "inteiro teor oficial", "identidade", "ratio decidendi", "aderência fática",
            "vigência/superação", "precedente contrário", "hash e trilha de auditoria"
        ],
    }


def validate_candidate(candidate: Candidate, document_path: str | Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "court": candidate.court, "case_number": candidate.case_number,
        "panel": candidate.panel, "rapporteur": candidate.rapporteur,
        "judgment_date": candidate.judgment_date, "holding": candidate.holding,
        "applicable_excerpt": candidate.applicable_excerpt,
        "excerpt_location": candidate.excerpt_location, "thesis": candidate.thesis,
        "outcome": candidate.outcome,
    }
    for key, value in required.items():
        if not str(value).strip():
            errors.append(f"campo obrigatório ausente: {key}")
    if not is_official_url(candidate.official_record_url):
        errors.append("URL do registro não pertence a domínio oficial .jus.br")
    if not is_official_url(candidate.full_text_url):
        errors.append("URL do inteiro teor não pertence a domínio oficial .jus.br")
    if not (CNJ_PATTERN.search(candidate.case_number) or re.search(r"[A-Za-z]+\s*\d+", candidate.case_number)):
        warnings.append("número/classe não segue padrão reconhecido; conferir manualmente")
    document_hash = None
    if document_path:
        path = Path(document_path)
        if not path.is_file() or path.stat().st_size == 0:
            errors.append("arquivo do inteiro teor ausente ou vazio")
        else:
            document_hash = sha256_file(path)
    else:
        errors.append("inteiro teor não foi fornecido para verificação")
    status = "CONFIRMADO" if not errors else "NÃO VALIDADO"
    return {
        "status": status,
        "checked_at": now_iso(),
        "candidate": asdict(candidate),
        "document_sha256": document_hash,
        "errors": errors,
        "warnings": warnings,
        "human_review_required": True,
    }


def finalize_validation(structural: dict[str, Any], review: LegalReview) -> dict[str, Any]:
    checks = {
        "excerpt_verified": review.excerpt_verified,
        "majority_reasoning_verified": review.majority_reasoning_verified,
        "factual_fit_verified": review.factual_fit_verified,
        "current_law_verified": review.current_law_verified,
        "adverse_authority_searched": review.adverse_authority_searched,
        "metadata_crosschecked": review.metadata_crosschecked,
    }
    missing = [name for name, passed in checks.items() if not passed]
    errors = list(structural.get("errors", []))
    if structural.get("status") != "CONFIRMADO":
        errors.append("validação estrutural não está CONFIRMADA")
    if not review.reviewer.strip():
        errors.append("revisor não identificado")
    if missing:
        errors.append("checagens jurídicas pendentes: " + ", ".join(missing))
    return {
        **structural,
        "status": "VALIDADO" if not errors else "NÃO VALIDADO",
        "legal_review": asdict(review),
        "legal_validation_at": now_iso(),
        "validation_errors": errors,
        "human_review_required": False if not errors else True,
    }


def append_audit(path: str | Path, event: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
