"""V1 — Autenticación de usuarios por access token.

osap-api valida el access token y extrae el ``user_id`` (UUID, claim ``sub``). Nunca
consulta la BD de osap-auth. La verificación de firma/JWKS es responsabilidad del
adaptador concreto (se inyecta vía :class:`IAuthenticator`); aquí se ofrecen dos
implementaciones: una estática (dev/tests) y una que decodifica el ``sub`` de un JWT.
"""

import base64
import json

from src.osap.ports.votes import IAuthenticator


class StaticTokenAuthenticator(IAuthenticator):
    """Devuelve un ``user_id`` fijo para un token concreto (dev/tests)."""

    def __init__(self, token: str, user_id: str) -> None:
        self._token = token
        self._user_id = user_id

    def user_id_for(self, token: str | None) -> str | None:
        if token is None:
            return None
        bearer = "Bearer "
        if token.startswith(bearer):
            token = token[len(bearer):]
        return self._user_id if token == self._token else None


class JwtAuthenticator(IAuthenticator):
    """Decodifica el ``sub`` de un JWT (Bearer token).

    NOTA: esta implementación no verifica la firma (el JWKS de osap-auth se valida en el
    adaptador de producción). Se inyecta vía el contenedor; en producción debe
    sustituirse por la verificación real contra el JWKS de osap-auth.
    """

    def user_id_for(self, token: str | None) -> str | None:
        if not token:
            return None
        bearer = "Bearer "
        if token.startswith(bearer):
            token = token[len(bearer):]
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return None
            payload = json.loads(_b64decode(parts[1]))
        except Exception:
            return None
        sub = payload.get("sub")
        return sub if isinstance(sub, str) and sub else None


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
