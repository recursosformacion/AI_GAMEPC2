"""Cliente OIDC *relying party* (osap-api → osap-auth como IdP).

Los metadatos del proveedor (authorization_endpoint, token_endpoint, jwks_uri) se
**descubren** desde el issuer vía `/.well-known/openid-configuration`, evitando fijar
URLs a mano. El cliente aporta solo: issuer, client_id, redirect_uri, scope y spa_origin.
El `client_secret` vive fuera (secret manager / entorno), nunca en la BD.
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
    """Fallo en el flujo OIDC (config ausente, discovery/canje fallido, etc.)."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class OidcRpClient:
    def __init__(
        self,
        issuer: str | None,
        client_id: str | None,
        client_secret: str | None,
        redirect_uri: str | None,
        spa_origin: str | None,
        scope: str = "openid profile",
    ) -> None:
        self._issuer = (issuer or "").rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._spa_origin = (spa_origin or "").rstrip("/")
        self._scope = scope
        self._discovered: dict[str, str] | None = None

    def configured(self) -> bool:
        return bool(
            self._issuer and self._client_id and self._redirect_uri and self._spa_origin
        )

    def _discover(self) -> dict[str, str]:
        """Descubre los endpoints del proveedor desde el well-known del issuer (con caché)."""
        if self._discovered is not None:
            return self._discovered
        if not self._issuer:
            raise OidcError("OIDC issuer no configurado")
        well_known = f"{self._issuer}/.well-known/openid-configuration"
        req = urllib.request.Request(
            well_known, headers={"Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (issuer confiado)
                doc = cast("dict[str, object]", json.loads(resp.read()))
        except Exception as exc:  # noqa: BLE001
            raise OidcError(f"OIDC discovery falló: {exc}") from exc
        auth = doc.get("authorization_endpoint")
        token = doc.get("token_endpoint")
        if not isinstance(auth, str) or not isinstance(token, str):
            raise OidcError("OIDC discovery sin authorization/token endpoint")
        self._discovered = {
            "authorization_endpoint": auth,
            "token_endpoint": token,
            "jwks_uri": str(doc.get("jwks_uri") or ""),
        }
        return self._discovered

    def generate_pkce(self) -> tuple[str, str]:
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        return verifier, challenge

    def generate_state(self) -> str:
        return secrets.token_urlsafe(24)

    def build_authorize_url(self, state: str, nonce: str, code_challenge: str) -> str:
        auth_endpoint = self._discover()["authorization_endpoint"]
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
        return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, code_verifier: str) -> dict[str, object]:
        token_endpoint = self._discover()["token_endpoint"]
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
            token_endpoint,
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
        # Se devuelven en el fragmento (#), no en la query: así no viajan al servidor
        # de la SPA ni quedan en logs/historial/referrer.
        params = urllib.parse.urlencode(
            {"access_token": access_token, "refresh_token": refresh_token}
        )
        return f"{self._spa_origin}/auth/callback#{params}"

    def error_callback_url(self, message: str) -> str:
        params = urllib.parse.urlencode({"error": message})
        return f"{self._spa_origin}/auth/callback?{params}"
