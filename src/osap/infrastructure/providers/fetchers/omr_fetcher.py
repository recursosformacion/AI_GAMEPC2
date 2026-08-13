"""Level-2 protocol adapter for the OpenMusicRepository storage operator (OMR).

The storage Provider API (`/api/v1/search`) returns a flat JSON *array* of file
records — not the `{"works": [...]}` contract shape — and filters on a single `q`
parameter. This fetcher calls that endpoint and normalizes each record into a Work
(with one MusicXML resource) that flows through the standard mapping pipeline, the
same way `MediaWikiFetcher` / `GitHubFetcher` do.
"""

import contextlib
import hashlib
import json
import urllib.parse
import urllib.request

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)
from src.osap.ports.service_token import IServiceTokenProvider

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class OmrStorageFetcher(ProviderFetcher):
    """OpenMusicRepository storage -> normalized contract JSON (works list)."""

    def __init__(
        self,
        base_url: str = "https://storage.openmusicrepository.com",
        timeout: int = 15,
        token_provider: IServiceTokenProvider | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token_provider = token_provider

    def fetch(
        self,
        definition: ProviderDefinition,
        endpoint: Endpoint,
        query: ProviderQuery,
    ) -> dict[str, object] | None:
        q = _build_query(query)
        if not q:
            return {"works": []}
        url = f"{self._base_url}/api/v1/search?q={urllib.parse.quote(q)}"
        headers: dict[str, str] = {"Accept": "application/json", "User-Agent": _USER_AGENT}
        if self._token_provider is not None:
            with contextlib.suppress(Exception):
                headers["Authorization"] = f"Bearer {self._token_provider.token(('storage:read',))}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (provider endpoint)
                data = json.loads(response.read())
        except Exception:
            return {"works": []}
        if not isinstance(data, list):
            return {"works": []}
        return {"works": [_to_work(record) for record in data]}

    def fetch_resource(
        self,
        definition: ProviderDefinition,
        endpoint: Endpoint,
        work_id: str,
    ) -> dict[str, object] | None:
        return None


def _to_work(record: dict[str, object]) -> dict[str, object]:
    remote_id = _remote_id(record)
    download = record.get("url")
    return {
        "id": remote_id,
        "title": str(record.get("title") or "Unknown"),
        "composer": record.get("composer"),
        "catalogue": None,
        "metadata": {
            "license": None,
            "public_domain": None,
        },
        "statistics": {},
        "resources": [
            {
                "id": remote_id,
                "format": "musicxml",
                "mime_type": "application/vnd.recordare.musicxml+xml",
                "available": bool(record.get("available", True)),
                "license": None,
                "links": {
                    "download": download,
                    "view": download,
                    "thumbnail": None,
                },
            }
        ],
    }


def _remote_id(record: dict[str, object]) -> str:
    file_id = record.get("file_id")
    if file_id is not None:
        return str(file_id)
    path = str(record.get("relative_path") or record.get("url") or "")
    return hashlib.sha1(path.encode()).hexdigest()[:16]  # noqa: S324


def _build_query(query: ProviderQuery) -> str:
    # The storage /api/v1/search filters on a single free-text `q`. A combined
    # "composer + title" string yields no matches, so prefer the most specific
    # single field (composer first, then title, then raw query).
    if query.composer:
        return query.composer
    if query.title:
        return query.title
    return (query.query or "").strip()
