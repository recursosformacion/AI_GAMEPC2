"""Cliente OIDC *relying party* (osap-api → osap-auth como IdP).

Genera PKCE (verifier/challenge), construye la URL de `authorize`, valida `state` y canjea
el `code` en `POST /oauth/token`. Los tokens de usuario resultantes (access/refresh) son
los que la Web almacena y usa en las APIs de usuario.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import cast


class OidcError(Exception):
    """Fallo en el flujo OIDC (config ausente, canje fallido, etc.)."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class OidcRpClient:
    def __init__(
        self,
        authorize_url: str | None,
        token_url: str | None,
        client_id: str | None,
        client_secret: str | None,
        redirect_uri: str | None,
        spa_origin: str | None,
        scope: str = "openid profile",
    ) -> None:
        self._authorize_url = authorize_url
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._spa_origin = (spa_origin or "").rstrip("/")
        self._scope = scope

    def configured(self) -> bool:
        return bool(
            self._authorize_url and self._token_url and self._client_id and self._redirect_uri
        )

    def generate_pkce(self) -> tuple[str, str]:
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        return verifier, challenge

    def generate_state(self) -> str:
        return secrets.token_urlsafe(24)

    def build_authorize_url(self, state: str, nonce: str, code_challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id or "",
            "redirect_uri": self._redirect_uri or "",
            "scope": self._scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self._authorize_url}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, code_verifier: str) -> dict[str, object]:
        if not (self._token_url and self._client_id):
            raise OidcError("OIDC token URL / client id no configurado")
        data = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "client_id": self._client_id or "",
                "client_secret": self._client_secret or "",
                "redirect_uri": self._redirect_uri or "",
                "code": code,
                "code_verifier": code_verifier,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self._token_url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (token endpoint confiado)
                return cast("dict[str, object]", json.loads(resp.read()))
        except urllib.error.HTTPError as exc:
            raise OidcError(f"OIDC token exchange failed (HTTP {exc.code})") from exc
        except Exception as exc:  # noqa: BLE001
            raise OidcError(f"OIDC token exchange error: {exc}") from exc

    def spa_callback_url(self, access_token: str, refresh_token: str) -> str:
        """URL a la que redirigir el navegador tras el canje, con la sesión para la SPA."""
        params = urllib.parse.urlencode(
            {"access_token": access_token, "refresh_token": refresh_token}
        )
        return f"{self._spa_origin}/auth/callback?{params}"
