"""V1 — Autenticación de usuarios y servicios por access token.

osap-api valida el access token y resuelve un :class:`Principal` a partir del claim
``token_use`` (``user`` / ``service``). Nunca consulta la BD de osap-auth. La verificación de
firma/JWKS es responsabilidad del adaptador concreto (se inyecta vía :class:`IAuthenticator`).

Compatibilidad de transición: los tokens sin ``token_use`` se resuelven con un fallback
**aislado** (ver :meth:`JwtAuthenticator._resolve_legacy`) que respeta la semántica de
osap-auth; no se introducen heurísticas nuevas.
"""

import base64
import json

from src.osap.domain.principal import Principal, ServicePrincipal, UserPrincipal
from src.osap.ports.votes import IAuthenticator


class StaticTokenAuthenticator(IAuthenticator):
    """Resuelve un ``UserPrincipal`` fijo para un token concreto (dev/tests).

    Permite configurar ``roles`` y ``email_verified`` para cubrir casos de autorización
    (p. ej. role=admin) sin depender de osap-auth.
    """

    def __init__(
        self,
        token: str,
        user_id: str,
        roles: tuple[str, ...] = ("user",),
        email_verified: bool = True,
    ) -> None:
        self._token = token
        self._user_id = user_id
        self._roles = roles
        self._email_verified = email_verified

    def resolve(self, token: str | None) -> Principal | None:
        if token is None:
            return None
        bearer = "Bearer "
        if token.startswith(bearer):
            token = token[len(bearer):]
        if token != self._token:
            return None
        return UserPrincipal(user_id=self._user_id, roles=self._roles, email_verified=self._email_verified)


class StaticServiceAuthenticator(IAuthenticator):
    """Resuelve un ``ServicePrincipal`` fijo para un token concreto (dev/tests)."""

    def __init__(self, token: str, service_id: str, scopes: tuple[str, ...] = ()) -> None:
        self._token = token
        self._service_id = service_id
        self._scopes = scopes

    def resolve(self, token: str | None) -> Principal | None:
        if token is None:
            return None
        bearer = "Bearer "
        if token.startswith(bearer):
            token = token[len(bearer):]
        if token != self._token:
            return None
        return ServicePrincipal(service_id=self._service_id, scopes=self._scopes)


class JwtAuthenticator(IAuthenticator):
    """Resuelve un ``Principal`` decodificando el payload de un JWT (Bearer token).

    NOTA: esta implementación no verifica la firma (el JWKS de osap-auth se valida en el
    adaptador de producción). Se inyecta vía el contenedor; en producción debe sustituirse por
    la verificación real contra el JWKS de osap-auth.
    """

    def resolve(self, token: str | None) -> Principal | None:
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
        return _principal_from_payload(payload)


def _principal_from_payload(payload: dict[str, object]) -> Principal | None:
    token_use = payload.get("token_use")
    if token_use == "user":
        return _user_from_payload(payload)
    if token_use == "service":
        return _service_from_payload(payload)
    # Transición: token sin `token_use`.
    return _resolve_legacy(payload)


def _user_from_payload(payload: dict[str, object]) -> UserPrincipal | None:
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    roles = payload.get("roles")
    roles_tuple = tuple(str(r) for r in roles) if isinstance(roles, list) else ("user",)
    email_verified = payload.get("email_verified")
    return UserPrincipal(
        user_id=sub,
        roles=roles_tuple or ("user",),
        email_verified=email_verified is True,
    )


def _service_from_payload(payload: dict[str, object]) -> ServicePrincipal | None:
    service_id = payload.get("sub") or payload.get("client_id")
    if not isinstance(service_id, str) or not service_id:
        return None
    scope = payload.get("scope")
    scopes = tuple(s for s in str(scope).split() if s) if isinstance(scope, str) and scope else ()
    return ServicePrincipal(service_id=service_id, scopes=scopes)


def _resolve_legacy(payload: dict[str, object]) -> Principal | None:
    """FALLBACK DE TRANSICIÓN (aislado): tokens sin ``token_use``.

    Respeta la semántica legada de osap-auth: un token con ``sub`` y ``roles`` es un usuario;
    un token con ``client_id``/``scope`` y sin roles es un servicio. Debe mantenerse aislado y
    documentado; se eliminará cuando ``token_use`` sea obligatorio.
    """
    if "client_id" in payload and "roles" not in payload:
        return _service_from_payload(payload)
    return _user_from_payload(payload)


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
