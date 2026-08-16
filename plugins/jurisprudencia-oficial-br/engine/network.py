from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import append_audit, now_iso
from .routing import CourtRouter


class SourceError(RuntimeError):
    pass


def request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None, retries: int = 2) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    merged = {"Accept": "application/json", "User-Agent": "jurisprudencia-oficial-br/0.1"}
    merged.update(headers or {})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, data=body, headers=merged, method=method)
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.25 * (2 ** attempt))
    raise SourceError(f"fonte indisponível ou resposta inválida: {last}")


def datajud_search(court: str, query: dict[str, Any]) -> dict[str, Any]:
    token = os.environ.get("DATAJUD_API_KEY", "").strip()
    if not token:
        raise SourceError("defina DATAJUD_API_KEY; credenciais não são armazenadas pelo plugin")
    slug = court.lower().replace("-", "")
    if slug not in CourtRouter().datajud_indexes():
        raise SourceError(f"índice DataJud não autorizado: {court}")
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{slug}/_search"
    return request_json(url, method="POST", payload=query, headers={
        "Authorization": f"APIKey {token}", "Content-Type": "application/json"
    })


def stj_open_data_search(term: str, rows: int = 20) -> dict[str, Any]:
    from urllib.parse import urlencode
    query = urlencode({"q": term, "rows": max(1, min(rows, 100))})
    return request_json(f"https://dadosabertos.web.stj.jus.br/api/3/action/package_search?{query}")


def probe_sources(config_path: str | Path, audit_path: str | Path | None = None) -> list[dict[str, Any]]:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    outcomes = []
    for source in config["sources"]:
        result = {"event": "source_probe", "source_id": source["id"], "url": source["base_url"],
                  "checked_at": now_iso(), "reachable": False, "healthy": False}
        try:
            req = Request(source["base_url"], headers={"User-Agent": "jurisprudencia-oficial-br/0.1"})
            with urlopen(req, timeout=15) as response:
                result.update({"reachable": True, "healthy": 200 <= response.status < 400, "status": response.status,
                               "final_url": response.geturl()})
        except HTTPError as exc:
            expected = exc.code in source.get("expected_probe_status", [])
            result.update({"reachable": True, "healthy": expected, "status": exc.code,
                           "credential_required": exc.code in (401, 403), "error": str(exc)})
        except (URLError, TimeoutError) as exc:
            result["error"] = str(exc)
            if "CERTIFICATE_VERIFY_FAILED" in str(exc):
                result["tls_verification_failed"] = True
        outcomes.append(result)
        if audit_path:
            append_audit(audit_path, result)
    return outcomes
