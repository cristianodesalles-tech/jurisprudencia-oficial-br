from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .authority import normalize_case_number
from .domain import JudicialDocument, is_official_url, normalize_text, utcnow
from .validation import OAB_PATTERN, NON_HUMAN_REVIEWERS, ReviewerNotIdentified

SUPERSEDED_PREFIX = "[ENTENDIMENTO SUPERADO]"
INJECTED_PREFIX = "[INJETADO DO REGISTRY]"
VALID_STATUS = {"superado", "parcialmente_superado", "modulado", "afetado"}


class OverrulingEntryError(ValueError):
    pass


def packaged_seed_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "overruling.json"


def default_registry_path() -> Path:
    """A curadoria mora no estado do usuário, não no pacote.

    O arquivo dentro do plugin é semente vazia e seria sobrescrito a cada atualização,
    levando junto o trabalho de curadoria do escritório.
    """
    from .runtime import default_state_dir
    return default_state_dir() / "overruling.json"


@dataclass
class OverrulingEntry:
    """Uma anotação de superação. Sempre curadoria humana com fonte oficial."""

    case_number: str
    court: str
    status: str
    nota: str
    fonte_url: str
    curador: str
    curador_oab: str
    superada_por: str = ""
    tema: str = ""
    registrado_em: str = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.status = normalize_text(self.status).lower()
        if self.status not in VALID_STATUS:
            raise OverrulingEntryError(f"status inválido: {self.status}; use um de {sorted(VALID_STATUS)}")
        if not normalize_text(self.case_number):
            raise OverrulingEntryError("informe o processo ou o enunciado superado")
        if not normalize_text(self.nota):
            raise OverrulingEntryError("descreva em uma frase o que foi superado e por quê")
        if not is_official_url(self.fonte_url):
            raise OverrulingEntryError("a superação precisa apontar para fonte oficial .jus.br")
        nome = normalize_text(self.curador)
        if len(nome.split()) < 2 or any(t.lower() in NON_HUMAN_REVIEWERS for t in nome.split()):
            raise ReviewerNotIdentified("o registro de superação exige o nome completo do curador")
        if not OAB_PATTERN.match(normalize_text(self.curador_oab).upper().replace("/", "").replace(".", "")):
            raise ReviewerNotIdentified("informe a inscrição OAB do curador, no formato UF 00000")

    @property
    def key(self) -> str:
        return normalize_case_number(self.case_number)


class OverrulingRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_registry_path()
        source = self.path if self.path.is_file() else packaged_seed_path()
        payload = json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {"entradas": []}
        self.entries: dict[str, OverrulingEntry] = {}
        for item in payload.get("entradas", []):
            entry = OverrulingEntry(**item)
            self.entries[entry.key] = entry

    def lookup(self, case_number: str) -> OverrulingEntry | None:
        return self.entries.get(normalize_case_number(case_number))

    def search(self, term: str) -> list[OverrulingEntry]:
        needle = normalize_text(term).lower()
        return [entry for entry in self.entries.values()
                if needle in f"{entry.case_number} {entry.tema} {entry.nota}".lower()]

    def add(self, entry: OverrulingEntry) -> OverrulingEntry:
        self.entries[entry.key] = entry
        self.save()
        return entry

    def save(self) -> None:
        payload = {"schema_version": 1,
                   "comentario": "Registro de superacao. Cada entrada exige fonte oficial e curador identificado.",
                   "entradas": [asdict(entry) for entry in self.entries.values()]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def annotate(self, document: JudicialDocument) -> bool:
        """Marca o documento se houver superação registrada. Não apaga nada."""
        entry = self.lookup(document.case_number)
        if entry is None:
            return False
        document.metadata = {**document.metadata,
                             "overruling_status": entry.status,
                             "overruling_nota": entry.nota,
                             "overruling_superada_por": entry.superada_por,
                             "overruling_fonte": entry.fonte_url,
                             "overruling_curador": entry.curador}
        if not document.title.startswith(SUPERSEDED_PREFIX):
            document.title = f"{SUPERSEDED_PREFIX} {document.title}".strip()
        return True

    def as_dicts(self) -> Iterable[dict[str, Any]]:
        return [asdict(entry) for entry in self.entries.values()]
