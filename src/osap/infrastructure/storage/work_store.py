"""V1 — Resolución de identidad de Work vía el contrato de Storage.

osap-api nunca accede a la BD de Storage. Solo pregunta por el ``composer_id`` de una
Work a través del contrato HTTP de Storage; si la Work no existe, devuelve ``None``
(HTTP 404).

Se ofrecen dos implementaciones: ``StorageWorkStore`` (contrato real de Storage) y
``MemoryWorkStore`` (en memoria, para tests y entornos sin Storage).
"""

import json
import urllib.parse
import urllib.request

from src.osap.ports.service_token import IServiceTokenProvider
from src.osap.ports.votes import IWorkStore

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class StorageWorkStore(IWorkStore):
    """Resuelve ``composer_id`` vía el contrato HTTP de Storage."""

    def __init__(
        self,
        base_url: str = "https://storage.openmusicrepository.com",
        timeout: int = 15,
        token_provider: IServiceTokenProvider | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token_provider = token_provider

    def composer_id_for(self, work_id: str) -> str | None:
        url = f"{self._base_url}/api/v1/works/{urllib.parse.quote(work_id)}"
        headers: dict[str, str] = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        if self._token_provider is not None:
            headers["Authorization"] = f"Bearer {self._token_provider.token(('storage:read',))}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (storage contract)
                doc: object = json.loads(response.read())
        except Exception:
            return None
        if not isinstance(doc, dict):
            return None
        composer_id = doc.get("composer_id")
        if isinstance(composer_id, str) and composer_id:
            return composer_id
        inner = doc.get("composer")
        if isinstance(inner, dict):
            nested = inner.get("composer_id")
            if isinstance(nested, str) and nested:
                return nested
        return None


class MemoryWorkStore(IWorkStore):
    """Mapa en memoria work_id -> composer_id (tests / sin Storage)."""

    def __init__(self, seed: dict[str, str] | None = None) -> None:
        self._map: dict[str, str] = dict(seed or {})

    def set(self, work_id: str, composer_id: str | None) -> None:
        if composer_id is None:
            self._map.pop(work_id, None)
        else:
            self._map[work_id] = composer_id

    def composer_id_for(self, work_id: str) -> str | None:
        return self._map.get(work_id)
