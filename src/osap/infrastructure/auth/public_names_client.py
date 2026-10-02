"""Cliente M2M del lookup de nombres públicos de osap-auth.

Consulta `GET /auth/m2m/users?ids=…` con un service token (`aud=osap-auth`, scope
`auth:read_public_names`), en lotes de ≤500 (máximo del endpoint). Devuelve `user_id → name`
(`name` puede ser `None`). Cualquier fallo se traduce a `CollaboratorsUnavailableError`.
"""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

import requests

from src.osap.application.collaborators import CollaboratorsUnavailableError

if TYPE_CHECKING:
    from src.osap.ports.service_token import IServiceTokenProvider

_NAMES_SCOPE = ("auth:read_public_names",)
_BATCH = 500


class PublicNamesClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8200",
        token_provider: IServiceTokenProvider,
        timeout: int = 15,
        batch_size: int = _BATCH,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._timeout = timeout
        self._batch_size = max(1, min(batch_size, _BATCH))

    def names(self, user_ids: list[str]) -> dict[str, str | None]:
        unicos = list(dict.fromkeys(uid for uid in user_ids if uid))
        resultado: dict[str, str | None] = {}
        for i in range(0, len(unicos), self._batch_size):
            resultado.update(self._fetch(unicos[i : i + self._batch_size]))
        return resultado

    def _fetch(self, ids: list[str]) -> dict[str, str | None]:
        try:
            token = self._token_provider.token(_NAMES_SCOPE)
        except Exception as exc:  # noqa: BLE001 — sin token no se puede consultar
            raise CollaboratorsUnavailableError(f"service token: {exc}") from exc
        query = urllib.parse.quote(",".join(ids), safe=",")
        url = f"{self._base_url}/auth/m2m/users?ids={query}"
        try:
            response = requests.get(
                url, headers={"Authorization": f"Bearer {token}"}, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise CollaboratorsUnavailableError(f"auth inaccesible: {exc}") from exc
        if response.status_code != 200:
            raise CollaboratorsUnavailableError(f"auth HTTP {response.status_code}")
        try:
            doc = response.json()
        except ValueError as exc:
            raise CollaboratorsUnavailableError("respuesta no JSON") from exc
        if not isinstance(doc, list):
            raise CollaboratorsUnavailableError("respuesta inesperada")
        return {
            str(item["id"]): item.get("name")
            for item in doc
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
