"""Cliente M2M del listado de reconocimientos activos por proyecto de osap-support.

Consulta `GET /api/v1/m2m/recognitions?project=…` con un service token (`aud=osap-support`,
scope `api:read`). Devuelve los reconocimientos ACTIVOS del proyecto agrupados por `user_id`,
sin filtrar por `public` (fila deprecada): la visibilidad la decide el consentimiento de
cuenta en osap-auth. Un 404 se traduce a `PublicProjectNotFoundError`; un fallo de red, de
token o HTTP ≠ 200, a `CollaboratorsUnavailableError`.
"""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

import requests

from src.osap.application.collaborators import (
    CollaboratorsUnavailableError,
    PublicProjectNotFoundError,
)
from src.osap.infrastructure.http.browser_headers import browser_headers

if TYPE_CHECKING:
    from src.osap.ports.service_token import IServiceTokenProvider

_SUPPORT_SCOPE = ("api:read",)


class SupportRecognitionsClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8300",
        token_provider: IServiceTokenProvider,
        timeout: int = 15,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._timeout = timeout

    def active_project_recognitions(self, project: str) -> list[dict[str, object]]:
        try:
            token = self._token_provider.token(_SUPPORT_SCOPE)
        except Exception as exc:  # noqa: BLE001 — sin token no se puede consultar
            raise CollaboratorsUnavailableError(f"service token: {exc}") from exc
        url = (
            f"{self._base_url}/api/v1/m2m/recognitions?"
            f"project={urllib.parse.quote(project)}"
        )
        try:
            response = requests.get(
                url,
                headers=browser_headers({"Authorization": f"Bearer {token}"}),
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise CollaboratorsUnavailableError(f"support inaccesible: {exc}") from exc
        if response.status_code == 404:
            raise PublicProjectNotFoundError(f"proyecto desconocido: {project}")
        if response.status_code != 200:
            raise CollaboratorsUnavailableError(f"support HTTP {response.status_code}")
        try:
            doc = response.json()
        except ValueError as exc:
            raise CollaboratorsUnavailableError("respuesta no JSON") from exc
        if not isinstance(doc, list):
            raise CollaboratorsUnavailableError("respuesta inesperada")
        filas: list[dict[str, object]] = []
        for item in doc:
            if not isinstance(item, dict):
                continue
            user_id = item.get("user_id")
            recs = item.get("recognitions")
            if not isinstance(user_id, str) or not isinstance(recs, list):
                continue
            filas.append(
                {
                    "user_id": user_id,
                    "recognitions": [
                        {"type": str(r["type"]), "granted_at": str(r["granted_at"])}
                        for r in recs
                        if isinstance(r, dict) and r.get("type")
                    ],
                }
            )
        return filas
