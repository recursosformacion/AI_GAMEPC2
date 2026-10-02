"""Cliente del listado público de reconocimientos por proyecto de osap-support.

Consulta `GET /api/v1/public/projects/{project}/recognitions` (sin autenticación; surface
pública de support). Un 404 se traduce a `PublicProjectNotFoundError`; un fallo de red o
HTTP ≥ 400, a `CollaboratorsUnavailableError`.
"""

from __future__ import annotations

import urllib.parse

import requests

from src.osap.application.collaborators import (
    CollaboratorsUnavailableError,
    PublicProjectNotFoundError,
)


class SupportPublicRecognitionsClient:
    def __init__(
        self, *, base_url: str = "http://127.0.0.1:8300", timeout: int = 15
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def public_project_recognitions(self, project: str) -> list[dict[str, object]]:
        url = (
            f"{self._base_url}/api/v1/public/projects/"
            f"{urllib.parse.quote(project)}/recognitions"
        )
        try:
            response = requests.get(url, timeout=self._timeout)
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
