from __future__ import annotations

import ipaddress
import json
import re
import socket
import ssl
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .domain import Provenance, SourceRole, stable_hash, utcnow


class ConnectorError(RuntimeError):
    pass


class AccessControlled(ConnectorError):
    pass


class UnsafeURL(ConnectorError):
    pass


@dataclass(frozen=True)
class FetchResult:
    content: bytes
    text: str
    provenance: Provenance
    suffix: str


def validate_official_url(url: str, *, resolve_dns: bool = True) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeURL("somente HTTPS oficial sem credenciais na URL")
    host = parsed.hostname.lower().rstrip(".")
    if not host.endswith(".jus.br"):
        raise UnsafeURL("host fora do domínio oficial .jus.br")
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise UnsafeURL(f"DNS não resolvido: {host}") from exc
        for raw in addresses:
            address = ipaddress.ip_address(raw)
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
                raise UnsafeURL("destino DNS aponta para rede não pública")
    return url


class _OfficialRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_official_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def extract_text(content: bytes, content_type: str) -> str:
    if "html" in content_type:
        parser = _TextExtractor()
        parser.feed(content.decode("utf-8", errors="replace"))
        return parser.text()
    if "json" in content_type:
        payload = json.loads(content.decode("utf-8"))
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if "text" in content_type or "xml" in content_type:
        return content.decode("utf-8", errors="replace")
    if "pdf" in content_type:
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except ImportError as exc:
            raise ConnectorError("instale pypdf para extrair PDFs") from exc
    raise ConnectorError(f"tipo de conteúdo não suportado: {content_type}")


class OfficialHttpConnector:
    def __init__(self, source_id: str, role: SourceRole, timeout: int = 30, max_bytes: int = 50_000_000):
        self.source_id, self.role, self.timeout, self.max_bytes = source_id, role, timeout, max_bytes
        self.opener = build_opener(_OfficialRedirectHandler())

    def fetch(self, url: str) -> FetchResult:
        validate_official_url(url)
        request = Request(url, headers={"User-Agent": "jurisprudencia-oficial-br/0.2 (+research; respectful)",
                                        "Accept": "application/pdf,text/html,application/json,text/plain;q=0.9"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                final_url = response.geturl()
                validate_official_url(final_url)
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length > self.max_bytes:
                    raise ConnectorError("documento excede o limite configurado")
                content = response.read(self.max_bytes + 1)
                if len(content) > self.max_bytes:
                    raise ConnectorError("documento excede o limite configurado")
                content_type = response.headers.get_content_type()
                text = extract_text(content, content_type)
                if len(text.strip()) < 40:
                    raise ConnectorError("conteúdo extraído insuficiente")
                provenance = Provenance(
                    source_id=self.source_id, source_url=url, retrieved_at=utcnow(),
                    content_sha256=stable_hash(content), role=self.role, http_status=response.status,
                    content_type=content_type, final_url=final_url,
                )
                suffix = {"application/pdf": ".pdf", "application/json": ".json", "text/html": ".html"}.get(content_type, ".bin")
                return FetchResult(content, text, provenance, suffix)
        except HTTPError as exc:
            if exc.code in (401, 403, 429):
                raise AccessControlled(f"acesso controlado ou limitado: HTTP {exc.code}") from exc
            raise ConnectorError(f"HTTP {exc.code}") from exc
        except ssl.SSLError as exc:
            raise ConnectorError("falha TLS; verificação não foi desativada") from exc
        except URLError as exc:
            raise ConnectorError(f"falha de rede: {exc.reason}") from exc


class SourceRegistry:
    def __init__(self, path: str | Path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.schema_version = payload["schema_version"]
        self.sources = {item["id"]: item for item in payload["sources"]}

    def get(self, source_id: str) -> dict[str, Any]:
        if source_id not in self.sources:
            raise KeyError(f"fonte desconhecida: {source_id}")
        return dict(self.sources[source_id])

    def validation_sources(self) -> list[dict[str, Any]]:
        return [dict(source) for source in self.sources.values() if source.get("validation_capability")]
