"""Cliente admin de reconocimientos de osap-support.

Usa un **service token** (`aud=osap-support`, scope `support:admin`) — la ruta admin de
support acepta servicio o usuario admin. Listar/conceder/revocar.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

from src.osap.infrastructure.http.browser_headers import browser_headers

if TYPE_CHECKING:
    from src.osap.ports.service_token import IServiceTokenProvider

_ADMIN_SCOPE = ("support:admin",)


class SupportAdminRecognitionsError(Exception):
    """osap-support no respondió correctamente a una operación admin de reconocimientos."""


class SupportAdminRecognitionsClient:
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

    @property
    def base_url(self) -> str:
        return self._base_url

    def admin_token(self) -> str:
        """Service token (`aud=osap-support`, scope `support:admin`) para la capa web propia."""
        return self._token_provider.token(_ADMIN_SCOPE)

    def _headers(self) -> dict[str, str]:
        token = self._token_provider.token(_ADMIN_SCOPE)
        return browser_headers(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def list_for_user(self, user_id: str) -> tuple[int, object]:
        query = urllib.parse.urlencode({"user_id": user_id})
        return self._call("GET", f"/api/v1/admin/recognitions?{query}")

    def grant(
        self, *, user_id: str, project: str, recognition_type: str, reason: str | None = None
    ) -> tuple[int, object]:
        payload: dict[str, object] = {
            "user_id": user_id, "project": project, "type": recognition_type
        }
        if reason:
            payload["reason"] = reason
        return self._call("POST", "/api/v1/admin/recognitions", payload)

    def revoke(self, *, recognition_id: int, reason: str | None = None) -> tuple[int, object]:
        payload: dict[str, object] = {}
        if reason:
            payload["reason"] = reason
        return self._call(
            "POST", f"/api/v1/admin/recognitions/{int(recognition_id)}/revoke", payload
        )

    def _call(
        self, method: str, path: str, payload: dict[str, object] | None = None
    ) -> tuple[int, object]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        try:
            headers = self._headers()
        except Exception as exc:  # noqa: BLE001
            raise SupportAdminRecognitionsError(f"service token: {exc}") from exc
        request = urllib.request.Request(
            self._base_url + path, data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                raw = response.read()
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                doc: object = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                doc = {}
            return exc.code, doc
        except Exception as exc:  # noqa: BLE001
            raise SupportAdminRecognitionsError(str(exc)) from exc
