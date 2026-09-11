"""Modelos YAML del adaptador genérico (Endpoint/ProviderDefinition/ProviderQuery/ProviderHttpClient)."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

_LOGGER = logging.getLogger("osap.providers.generic")


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    name: str
    base_url: str
    endpoints: dict[str, Endpoint]
    work_mapping: dict[str, str]
    resource_mapping: dict[str, str]
    resource_list: str = "resources"
    request_mapping: dict[str, str] = field(default_factory=dict)
    authentication: str | None = None
    # Optional field transformations (from transforms.yaml) applied during mapping.
    # Shape: {"fields": {field: [ops]}, "resources": {field: [ops]}}
    transforms: dict[str, object] = field(default_factory=dict)


@dataclass
class ProviderQuery:
    query: str = ""
    composer: str | None = None
    catalogue: str | None = None
    title: str | None = None
    page: int = 1
    limit: int = 50


class ProviderHttpClient:
    def __init__(self, base_url: str, accept: str) -> None:
        self._base_url = base_url
        self._accept = accept

    def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object] | None:
        url = self._base_url + path
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": self._accept, "User-Agent": "Mozilla/5.0 (OSAP provider adapter)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (provider endpoint)
                data = json.loads(resp.read())
        except Exception:  # noqa: BLE001 — un proveedor caído no debe tumbar la búsqueda
            _LOGGER.warning("Provider HTTP GET falló: %s", url, exc_info=True)
            return None
        return data if isinstance(data, dict) else None


