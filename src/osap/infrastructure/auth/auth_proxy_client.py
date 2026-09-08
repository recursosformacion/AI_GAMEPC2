"""V1 — Proxy de identidad de usuario hacia osap-auth (registro/verificación).

Operaciones de **usuario/identidad** (públicas): osap-api reenvía a osap-auth SIN service
token (no es una operación entre servicios). No crea usuarios en osap-api ni toca su BD.
osap-auth es la autoridad de identidad.
"""

import json
import urllib.error
import urllib.request


class AuthProxyError(Exception):
    """osap-auth no respondió correctamente a una operación de identidad."""


class AuthProxyClient:
    """Cliente de las operaciones públicas de identidad de osap-auth."""

    def __init__(self, base_url: str, timeout: int = 15) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def register(self, email: str, password: str, name: str | None = None) -> tuple[int, dict[str, object]]:
        payload: dict[str, object] = {"email": email, "password": password}
        if name:
            payload["name"] = name
        return self._call("POST", "/auth/register", payload)

    def verify_email(self, token: str) -> tuple[int, dict[str, object]]:
        return self._call("POST", "/auth/verify-email", {"token": token})

    # -- administración de usuarios (role=admin en osap-auth) -----------------

    def admin_users(self, access_token: str) -> tuple[int, object]:
        return self._call_bearer("GET", "/auth/admin/users", access_token)

    def admin_user(self, access_token: str, user_id: str) -> tuple[int, object]:
        return self._call_bearer("GET", f"/auth/admin/users/{user_id}", access_token)

    def admin_update_user(
        self, access_token: str, user_id: str, payload: dict[str, object]
    ) -> tuple[int, object]:
        return self._call_bearer("PATCH", f"/auth/admin/users/{user_id}", access_token, payload)

    # -- helpers -------------------------------------------------------------

    def _call_bearer(
        self,
        method: str,
        path: str,
        access_token: str,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        # El header que llega de la app puede incluir el esquema ("Bearer eyJ…"). Se
        # normaliza para no generar "Bearer Bearer …" al reenviar a osap-auth.
        token = access_token
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        url = self._base_url + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                raw = response.read()
                doc: object = json.loads(raw) if raw else {}
                return response.status, doc
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                doc = json.loads(raw or b"{}") if raw else {}
            except Exception:
                doc = {}
            return exc.code, doc
        except Exception as exc:
            raise AuthProxyError(str(exc)) from exc

    def _call(self, method: str, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        url = self._base_url + path
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (auth identity endpoint)
                raw = response.read()
                doc: dict[str, object] = json.loads(raw) if raw else {}
                return response.status, doc
        except urllib.error.HTTPError as exc:
            try:
                doc = json.loads(exc.read() or b"{}") if exc.read() else {}
            except Exception:
                doc = {}
            return exc.code, doc
        except Exception as exc:
            raise AuthProxyError(str(exc)) from exc
