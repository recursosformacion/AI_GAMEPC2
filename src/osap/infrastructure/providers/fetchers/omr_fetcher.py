"""Level-2 protocol adapter for the OpenMusicRepository storage operator (OMR).

The storage Provider API (`/api/search`) returns the `{"works": [...]}` contract
shape, filtered by a single `q` parameter. This fetcher calls that endpoint and
normalizes each Work (with its resources) into the standard mapping pipeline, the
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
        # Usa el CONTRATO de proveedor de storage (/api/search), no la búsqueda pública
        # (/api/v1/search): devuelve {works:[...]} con resources[].links.download.
        url = f"{self._base_url}/api/search?q={urllib.parse.quote(q)}"
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
        if isinstance(data, dict):
            works = data.get("works") or []
            data = works if isinstance(works, list) else []
        if not isinstance(data, list):
            return {"works": []}
        # Se conservan TODAS las obras: las de CPDL están identificadas en `works` aunque
        # todavía no tengan un recurso descargable (materialización pendiente).
        return {"works": [_to_work(record, self._base_url) for record in data]}

    def fetch_resource(
        self,
        definition: ProviderDefinition,
        endpoint: Endpoint,
        work_id: str,
    ) -> dict[str, object] | None:
        return None


def _absolute(base_url: str, path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _to_work(record: dict[str, object], base_url: str) -> dict[str, object]:
    remote_id = _remote_id(record)
    resources_raw = record.get("resources")
    resources = resources_raw if isinstance(resources_raw, list) else []
    first = resources[0] if resources and isinstance(resources[0], dict) else {}
    links_raw = first.get("links") if isinstance(first, dict) else None
    links = links_raw if isinstance(links_raw, dict) else {}
    download = _absolute(base_url, str(links.get("download") or ""))
    available = bool(first.get("available", True)) if isinstance(first, dict) else True
    resources_out: list[dict[str, object]] = []
    if first:
        resources_out.append(
            {
                "id": remote_id,
                "format": "musicxml",
                "mime_type": "application/vnd.recordare.musicxml+xml",
                "available": available,
                "license": None,
                "links": {
                    "download": download,
                    "view": download,
                    "thumbnail": None,
                },
            }
        )
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
        # Obra identificada sin recurso descargable (p. ej. CPDL en inventario): sin recursos.
        "resources": resources_out,
    }


def _remote_id(record: dict[str, object]) -> str:
    remote_id = record.get("id")
    if remote_id is not None and str(remote_id).strip():
        return str(remote_id)
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
