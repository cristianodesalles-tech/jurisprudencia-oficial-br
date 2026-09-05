from __future__ import annotations

import ipaddress
import html
import http.cookiejar
import json
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener

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

    def assisted_sources(self) -> list[dict[str, Any]]:
        return [dict(source) for source in self.sources.values() if source.get("access_mode") == "assisted"]


class TRF1SearchConnector:
    """Pesquisa acórdãos no formulário JSF público mantido pelo CJF, com baixa cadência."""

    base_url = "https://jurisprudencia.cjf.jus.br"
    search_url = base_url + "/trf1/index.xhtml"

    def __init__(self, timeout: int = 45, min_interval: float = 2.0, max_bytes: int = 15_000_000):
        self.timeout, self.min_interval, self.max_bytes = timeout, min_interval, max_bytes
        self._lock, self._last_request = threading.Lock(), 0.0

    def _fetch(self, query: str) -> str:
        if len(query.strip()) < 3:
            raise ConnectorError("consulta TRF1 deve ter ao menos três caracteres")
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            jar = http.cookiejar.CookieJar()
            opener = build_opener(_OfficialRedirectHandler(), HTTPCookieProcessor(jar))
            headers = {"User-Agent": "jurisprudencia-oficial-br/0.3 (+research; respectful)"}
            try:
                initial = opener.open(Request(self.base_url + "/trf1", headers=headers), timeout=self.timeout).read(2_000_001)
                if len(initial) > 2_000_000:
                    raise ConnectorError("página inicial TRF1 excede o limite")
                page = initial.decode("utf-8", errors="replace")
                states = re.findall(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)', page)
                if not states:
                    raise ConnectorError("ViewState do TRF1 não encontrado")
                body = urlencode([
                    ("formulario", "formulario"), ("formulario:textoLivre", query.strip()),
                    ("formulario:selectTiposDocumento", "ACORDAO"), ("formulario:j_idt62", "TRF1"),
                    ("formulario:actPesquisar", ""), ("javax.faces.ViewState", html.unescape(states[-1])),
                ]).encode()
                request = Request(self.search_url, data=body, headers={**headers,
                    "Content-Type": "application/x-www-form-urlencoded", "Origin": self.base_url,
                    "Referer": self.base_url + "/trf1"})
                raw = opener.open(request, timeout=self.timeout).read(self.max_bytes + 1)
                if len(raw) > self.max_bytes:
                    raise ConnectorError("resultado TRF1 excede o limite")
                return raw.decode("utf-8", errors="replace")
            except HTTPError as exc:
                if exc.code in (401, 403, 429):
                    raise AccessControlled(f"TRF1 controlado ou limitado: HTTP {exc.code}") from exc
                raise ConnectorError(f"TRF1 respondeu HTTP {exc.code}") from exc
            except URLError as exc:
                raise ConnectorError(f"falha de rede TRF1: {exc.reason}") from exc
            finally:
                self._last_request = time.monotonic()

    @staticmethod
    def _text(value: str) -> str:
        value = re.sub(r"(?i)<br\s*/?>", " ", value)
        value = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    @classmethod
    def _field(cls, block: str, label: str) -> str:
        match = re.search(rf'<span class="label_pontilhada">{re.escape(label)}</span>.*?</tr>\s*<tr>\s*<td[^>]*>(.*?)</td>', block, re.I | re.S)
        return cls._text(match.group(1)) if match else ""

    @staticmethod
    def _date(value: str) -> str | None:
        match = re.search(r"\d{2}/\d{2}/\d{4}", value)
        return datetime.strptime(match.group(), "%d/%m/%Y").date().isoformat() if match else None

    @classmethod
    def parse(cls, page: str, limit: int = 10) -> list[dict[str, Any]]:
        starts = list(re.finditer(r'<div id="item_resultado-(\d+)">', page))
        results = []
        for index, start in enumerate(starts[:min(max(limit, 1), 10)]):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(page)
            block, identifier = page[start.start():end], start.group(1)
            number = cls._field(block, "Número").split(" ")[0]
            excerpt = cls._field(block, "Ementa")
            if not number or not excerpt:
                continue
            link = re.search(r'https://(?:arquivo|pje2g)\.trf1\.jus\.br/[^"&<]+', html.unescape(block))
            results.append({
                "id": f"trf1:{identifier}", "court": "TRF1", "type": cls._field(block, "Tipo") or "Acórdão",
                "case_number": number, "rapporteur": cls._field(block, "Relator(a)") or None,
                "chamber": cls._field(block, "Órgão julgador") or None,
                "judgment_date": cls._date(cls._field(block, "Data")),
                "publication_date": cls._date(cls._field(block, "Data da publicação")),
                "excerpt": excerpt[:12000], "status": "NÃO VALIDADO", "source_url": cls.search_url,
                "full_text_url": link.group(0) if link else None,
            })
        return results

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.parse(self._fetch(query), limit)
