"""Level-2 protocol adapter for MusicBrainz.

MusicBrainz es una base de datos de obras/artistas (metadata, sin ficheros de partitura).
Su API REST pública devuelve `works[]` con compositores (relations composer). Este fetcher
normaliza cada Work al contrato del proveedor y entrega el **enlace** a la obra en MusicBrainz
(página + API JSON). Se entrega lo que el proveedor da (metadata + link); no hay fichero.
"""

import json
import urllib.parse
import urllib.request

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)

_API_BASE = "https://musicbrainz.org/ws/2"
_WEB_BASE = "https://musicbrainz.org"
_USER_AGENT = "osap-api/0.1 (https://github.com/recursosformacion/AI_GAMEPC2)"
_MAX_LIMIT = 100


class MusicBrainzFetcher(ProviderFetcher):
    """MusicBrainz work search -> normalized contract JSON (works list)."""

    def __init__(self, timeout: int = 20) -> None:
        self._timeout = timeout

    def fetch(
        self, definition: ProviderDefinition, endpoint: Endpoint, query: ProviderQuery
    ) -> dict[str, object] | None:
        lucene = _build_query(query)
        if not lucene:
            return {"works": []}
        limit = min(int(query.limit) if query.limit else 25, _MAX_LIMIT)
        path = f"/work/?query={urllib.parse.quote(lucene)}&fmt=json&limit={limit}"
        request = urllib.request.Request(
            f"{_API_BASE}{path}",
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (public API)
                doc = json.loads(response.read())
        except Exception:
            return {"works": []}
        works = doc.get("works") if isinstance(doc, dict) else []
        if not isinstance(works, list):
            works = []
        return {"works": [_to_work(w) for w in works if isinstance(w, dict)]}

    def fetch_resource(
        self, definition: ProviderDefinition, endpoint: Endpoint, work_id: str
    ) -> dict[str, object] | None:
        return None


def _build_query(query: ProviderQuery) -> str:
    parts: list[str] = []
    if query.composer:
        parts.append(f'artist:"{_escape(query.composer)}"')
    if query.title:
        parts.append(f'work:"{_escape(query.title)}"')
    elif query.query:
        parts.append(f'work:"{_escape(query.query)}"')
    return " AND ".join(parts)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _to_work(entry: dict[str, object]) -> dict[str, object]:
    work_id = str(entry.get("id") or "")
    title = str(entry.get("title") or "Unknown")
    composer = _composer_of(entry)
    # MusicBrainz no tiene fichero de partitura: se expone como metadata con enlace a la
    # PÁGINA web humana (no al JSON de la API). available=False -> la UI ofrece "abrir en MB".
    web_url = f"{_WEB_BASE}/work/{work_id}" if work_id else None
    return {
        "id": work_id or _stable_id(title + (composer or "")),
        "title": title,
        "composer": composer,
        "catalogue": None,
        "license": None,
        "public_domain": None,
        "resources": [
            {
                "id": work_id or _stable_id(title),
                "format": "json",
                "mime_type": "application/json",
                "available": False,
                "license": None,
                "download_url": web_url,
                "view_url": web_url,
                "thumbnail_url": None,
            }
        ],
    }


def _composer_of(entry: dict[str, object]) -> str | None:
    relations = entry.get("relations")
    if not isinstance(relations, list):
        return None
    for relation in relations:
        if not isinstance(relation, dict) or relation.get("type") != "composer":
            continue
        artist = relation.get("artist")
        if not isinstance(artist, dict):
            continue
        name = artist.get("name")
        if isinstance(name, str) and name:
            return name
    return None


def _stable_id(value: str) -> str:
    import hashlib

    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]  # noqa: S324
