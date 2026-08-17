"""Level-2 protocol adapter for RISM (opac, VuFind RSS search).

RISM cataloga manuscritos musicales. Su opac expone un search RSS:
`Search/Results?lookfor={q}&view=rss`. Los títulos siguen "Compositor: Obra, ...".
Este fetcher normaliza al contrato del proveedor (works con compositor), refinando:

  - descarta colecciones multi-compositor ("Finney, Hugh, Walker: ..." -> 3 nombres);
  - filtra por similitud de título de la obra con la query;
  - conserva "Anonymus"/"Anonymous" (atribución explícita de fuente, ADR-0034).
"""

from __future__ import annotations

import hashlib
import html
import re
import ssl
import urllib.parse
import urllib.request

from src.osap.application.metadata_normalizer import title_key, title_similarity
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)

_OPAC = "https://opac.rism.info/rism/Search/Results"
_UA = "osap-rism-fetcher/0.1 (reconstruction; read-only)"
_CTX = ssl._create_unverified_context()  # entorno con store de certs roto

_TITLE_RE = re.compile(r"<item>\s*<title>(.*?)</title>", re.S)
_MIN_SIMILARITY = 0.4


class RismFetcher(ProviderFetcher):
    """RISM (opac RSS) -> normalized contract JSON."""

    def fetch(
        self, definition: ProviderDefinition, endpoint: Endpoint, query: ProviderQuery
    ) -> dict[str, object] | None:
        title = (query.title or query.query or "").strip()
        if not title:
            return {"works": []}
        target = title_key(title)
        works: list[dict[str, object]] = []
        for composer, work_title in self._search(title):
            if not _is_single_attribution(composer):
                continue
            if title_similarity(target, title_key(work_title)) < _MIN_SIMILARITY and _is_anonymous(
                composer
            ) is False:
                continue
            works.append(_to_work(work_title, composer))
        return {"works": works}

    def fetch_resource(
        self, definition: ProviderDefinition, endpoint: Endpoint, work_id: str
    ) -> dict[str, object] | None:
        return None

    def _search(self, title: str) -> list[tuple[str, str]]:
        url = f"{_OPAC}?lookfor={urllib.parse.quote(title)}&view=rss"
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/xml"}),
                timeout=30,
                context=_CTX,
            ) as response:
                body = response.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return []
        out: list[tuple[str, str]] = []
        for match in _TITLE_RE.finditer(body):
            item = html.unescape(match.group(1)).strip()
            if ":" not in item:
                continue
            composer, work_title = item.split(":", 1)
            composer = composer.strip()
            work_title = work_title.strip(" ,;.")
            if composer and work_title:
                out.append((composer, work_title))
        return out


def _to_work(title: str, composer: str) -> dict[str, object]:
    work_id = hashlib.sha1(title.encode()).hexdigest()[:16]  # noqa: S324
    return {
        "id": work_id,
        "title": title,
        "composer": composer,
        "catalogue": None,
        "license": None,
        "public_domain": None,
        "resources": [
            {
                "id": work_id,
                "format": "rss",
                "mime_type": "application/rss+xml",
                "available": True,
                "license": None,
                "download_url": None,
                "view_url": f"https://opac.rism.info/search?query={urllib.parse.quote(title)}",
                "thumbnail_url": None,
            }
        ],
    }


def _is_single_attribution(composer: str) -> bool:
    # Colección multi-compositor ("A, B, C") no es una atribución única.
    names = [part.strip() for part in composer.split(",") if part.strip()]
    return _is_anonymous(composer) or len(names) < 2


def _is_anonymous(composer: str) -> bool:
    return composer.lower() in ("anonymus", "anonymous", "anon", "trad", "traditional")
