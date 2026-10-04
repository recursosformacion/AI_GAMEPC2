"""Cliente M2M del lookup de perfiles públicos de osap-auth.

Consulta `GET /auth/m2m/users?ids=…` con un service token (`aud=osap-auth`, scope
`auth:read_public_names`), en lotes de ≤500 (máximo del endpoint). Devuelve
`user_id → PublicProfile` (nickname + consentimiento de cuenta). Cualquier fallo se traduce a
`CollaboratorsUnavailableError`.
"""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

import requests

from src.osap.application.collaborators import (
    CollaboratorsUnavailableError,
    PublicProfile,
    PublicUser,
)

if TYPE_CHECKING:
    from src.osap.ports.service_token import IServiceTokenProvider

_PROFILES_SCOPE = ("auth:read_public_names",)
_BATCH = 500


class PublicProfilesClient:
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

    def public_users(self) -> list[PublicUser]:
        """Usuarios públicos de osap-auth (consentimiento + nickname), sin `user_id` expuesto."""
        try:
            token = self._token_provider.token(_PROFILES_SCOPE)
        except Exception as exc:  # noqa: BLE001 — sin token no se puede consultar
            raise CollaboratorsUnavailableError(f"service token: {exc}") from exc
        url = f"{self._base_url}/auth/m2m/public-users"
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
        usuarios: list[PublicUser] = []
        for item in doc:
            if not isinstance(item, dict):
                continue
            user_id = item.get("id")
            nickname = item.get("nickname")
            if isinstance(user_id, str) and isinstance(nickname, str) and nickname:
                usuarios.append(PublicUser(user_id=user_id, nickname=nickname))
        return usuarios

    def public_profiles(self, user_ids: list[str]) -> dict[str, PublicProfile]:
        unicos = list(dict.fromkeys(uid for uid in user_ids if uid))
        resultado: dict[str, PublicProfile] = {}
        for i in range(0, len(unicos), self._batch_size):
            resultado.update(self._fetch(unicos[i : i + self._batch_size]))
        return resultado

    def _fetch(self, ids: list[str]) -> dict[str, PublicProfile]:
        try:
            token = self._token_provider.token(_PROFILES_SCOPE)
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
        perfiles: dict[str, PublicProfile] = {}
        for item in doc:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            nickname = item.get("nickname")
            perfiles[str(item["id"])] = PublicProfile(
                nickname=nickname if isinstance(nickname, str) else None,
                nickname_public_consent=bool(item.get("nickname_public_consent")),
            )
        return perfiles
