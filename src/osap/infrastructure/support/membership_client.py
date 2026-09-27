"""Cliente M2M de membresía de osap-support (fase 4.2, paso 5).

Consulta `GET /api/v1/m2m/membership?user_id=…` con un service token (`api:read`). Un error
de red, de autenticación o HTTP ≥ 400 se traduce a `SupportUnavailableError` para que el
reconciliador lo trate como **consulta no fiable** (no como membresía inactiva).
"""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

import requests

from src.osap.application.reconcile_membership import (
    MembershipSnapshot,
    SupportUnavailableError,
)

if TYPE_CHECKING:
    from src.osap.ports.service_token import IServiceTokenProvider

_SUPPORT_SCOPE = ("api:read",)


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


class SupportMembershipClient:
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

    def fetch(self, user_id: str) -> MembershipSnapshot:
        try:
            token = self._token_provider.token(_SUPPORT_SCOPE)
        except Exception as exc:  # noqa: BLE001 — sin token no se puede consultar
            raise SupportUnavailableError(f"service token: {exc}") from exc
        url = f"{self._base_url}/api/v1/m2m/membership?user_id={urllib.parse.quote(user_id)}"
        try:
            response = requests.get(
                url, headers={"Authorization": f"Bearer {token}"}, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise SupportUnavailableError(f"support inaccesible: {exc}") from exc
        # 401/403 o 5xx NO significan inactividad: consulta no fiable.
        if response.status_code != 200:
            raise SupportUnavailableError(f"support HTTP {response.status_code}")
        try:
            doc = response.json()
        except ValueError as exc:
            raise SupportUnavailableError("respuesta no JSON") from exc
        if not isinstance(doc, dict):
            raise SupportUnavailableError("respuesta inesperada")
        return MembershipSnapshot(
            active=bool(doc.get("active")),
            tier=_str_or_none(doc.get("tier")),
            valid_from=_str_or_none(doc.get("valid_from")),
            valid_until=_str_or_none(doc.get("valid_until")),
            source=_str_or_none(doc.get("source")),
        )
