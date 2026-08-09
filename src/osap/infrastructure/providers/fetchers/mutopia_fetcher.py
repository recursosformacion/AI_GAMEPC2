"""Level-2 protocol adapter for the Mutopia Project.

Mutopia has no JSON API: it exposes a search CGI (`cgibin/make-table.cgi`) that
returns an HTML table where each piece spans 5 consecutive rows (title/composer,
instrumentation, publisher/license, download links, PDF links). This fetcher calls
that endpoint, parses the table, and normalizes each piece into a Work with a PDF and
a MIDI resource that flows through the standard mapping pipeline.
"""

import hashlib
import html as _html
import re
import urllib.parse
import urllib.request

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_LINK_RE = re.compile(r'href="([^"]+)"')


class MutopiaFetcher(ProviderFetcher):
    """Mutopia (HTML table CGI) -> normalized contract JSON (works list)."""

    def __init__(
        self,
        base_url: str = "https://www.mutopiaproject.org",
        timeout: int = 20,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def fetch(
        self,
        definition: ProviderDefinition,
        endpoint: Endpoint,
        query: ProviderQuery,
    ) -> dict[str, object] | None:
        term = _build_term(query)
        if not term:
            return {"works": []}
        url = f"{self._base_url}/cgibin/make-table.cgi?{urllib.parse.urlencode({'searchingfor': term})}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = response.read().decode("utf-8", "replace")
        except Exception:
            return {"works": []}
        return {"works": _parse_table(body)}

    def fetch_resource(
        self,
        definition: ProviderDefinition,
        endpoint: Endpoint,
        work_id: str,
    ) -> dict[str, object] | None:
        return None


def _parse_table(body: str) -> list[dict[str, object]]:
    rows: list[tuple[list[str], list[str]]] = []
    for raw in _ROW_RE.findall(body):
        cells = [_strip_tags(td) for td in _TD_RE.findall(raw)]
        links = _LINK_RE.findall(raw)
        rows.append((cells, links))

    works: list[dict[str, object]] = []
    i = 0
    while i < len(rows):
        cells, links = rows[i]
        # A piece's download row starts with "Download: .ly file".
        if cells and cells[0].startswith("Download:") and i >= 3 and i + 1 < len(rows):
            work = _build_work(rows, i)
            if work:
                works.append(work)
            i += 2
            continue
        i += 1
    return works


def _build_work(rows: list[tuple[list[str], list[str]]], i: int) -> dict[str, object] | None:
    title_cells, _ = rows[i - 3]
    pub_cells, pub_links = rows[i - 1]
    _, dl_links = rows[i]
    _, pdf_links = rows[i + 1]

    title = _text(title_cells[0]) if title_cells else ""
    composer = _extract_composer(title_cells) if len(title_cells) > 1 else None
    if not title:
        return None

    piece_id = next((lnk.split("id=")[-1] for lnk in pub_links if "piece-info.cgi?id=" in lnk), None)
    remote_id = piece_id or hashlib.sha1(f"{title}|{composer}".encode()).hexdigest()[:16]  # noqa: S324

    license_text = _text(pub_cells[1]) if len(pub_cells) > 1 else ""
    public_domain = "public domain" in license_text.lower()
    license_value = "public domain" if public_domain else (license_text or None)

    pdf_url = next((lnk for lnk in pdf_links if lnk.endswith(".pdf")), None)
    midi_url = next((lnk for lnk in dl_links if lnk.endswith(".mid")), None)
    preview = next((lnk for lnk in dl_links if "preview" in lnk), None)

    resources: list[dict[str, object]] = []
    if pdf_url:
        resources.append(_resource(f"{remote_id}-pdf", "pdf", "application/pdf", pdf_url, preview))
    if midi_url:
        resources.append(_resource(f"{remote_id}-mid", "midi", "audio/midi", midi_url, preview))

    return {
        "id": remote_id,
        "title": title,
        "composer": composer,
        "catalogue": None,
        "license": license_value,
        "public_domain": public_domain,
        "resources": resources,
    }


def _resource(resource_id: str, fmt: str, mime: str, url: str, preview: str | None) -> dict[str, object]:
    return {
        "id": resource_id,
        "format": fmt,
        "mime_type": mime,
        "available": True,
        "license": None,
        "download_url": url,
        "view_url": url,
        "thumbnail_url": preview,
    }


def _extract_composer(title_cells: list[str]) -> str | None:
    raw = _text(title_cells[1])
    if raw.startswith("by "):
        return raw[3:].strip() or None
    return raw.strip() or None


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return _html.unescape(text).strip()


def _text(cell: str) -> str:
    return cell.strip()


def _build_term(query: ProviderQuery) -> str:
    if query.composer:
        return query.composer
    if query.title:
        return query.title
    return (query.query or "").strip()
