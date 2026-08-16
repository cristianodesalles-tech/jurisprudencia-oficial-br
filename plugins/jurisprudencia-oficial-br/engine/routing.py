from __future__ import annotations

import json
from pathlib import Path


class CourtRouter:
    def __init__(self, config: str | Path | None = None):
        path = Path(config) if config else Path(__file__).resolve().parents[1] / "config" / "courts.json"
        self.config = json.loads(path.read_text(encoding="utf-8"))

    def route(self, branch: str, state: str) -> dict[str, list[str] | str]:
        state = state.upper().strip()
        if state not in self.config["state"]:
            raise ValueError(f"UF inválida: {state}")
        branch = branch.lower().strip()
        if branch in {"trabalho", "trabalhista", "labor"}:
            locals_ = self.config["labor"][state]
            return {"local": locals_, "superior": ["TST"], "constitutional": ["STF"]}
        if branch in {"federal", "justiça federal"}:
            return {"local": [self.config["federal"][state]], "superior": ["STJ"], "constitutional": ["STF"]}
        return {"local": [self.config["state"][state]], "superior": ["STJ"], "constitutional": ["STF"]}

    def datajud_indexes(self) -> set[str]:
        courts = set(self.config["state"].values())
        courts.update(value for values in self.config["labor"].values() for value in values)
        courts.update(self.config["federal"].values())
        courts.update({"STJ", "TST"})
        return {court.lower() for court in courts}
