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
import time
from collections.abc import Callable
from typing import Any

import jwt
import requests

from src.osap.domain.principal import Principal, ServicePrincipal, UserPrincipal
from src.osap.ports.votes import IAuthenticator

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


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


class JwksJwtAuthenticator(IAuthenticator):
    """Verifica firma RS256 contra el JWKS de osap-auth (selección por `kid`) y los claims
    del contrato (iss/aud/exp/iat/jti) antes de resolver el `Principal`.

    Un token manipulado, con firma inválida, `kid` desconocido o expirado se rechaza
    (devuelve `None`); no se confía en el payload decodificado.
    """

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        clock_skew_seconds: int = 60,
        timeout_seconds: float = 10.0,
        cache_ttl_seconds: float = 3600.0,
        jwks_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        if not jwks_url or not issuer or not audience:
            raise ValueError("jwks_url/issuer/audience son obligatorios")
        self._jwks_url = jwks_url
        self._issuer = issuer
        self._audience = audience
        self._leeway = clock_skew_seconds
        self._timeout = timeout_seconds
        self._cache_ttl = cache_ttl_seconds
        self._jwks_provider = jwks_provider
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_fetched_at = 0.0

    def resolve(self, token: str | None) -> Principal | None:
        if not token:
            return None
        bearer = "Bearer "
        if token.startswith(bearer):
            token = token[len(bearer):]
        try:
            header = jwt.get_unverified_header(token)
            key = self._verification_key(header.get("kid"))
            if key is None:
                return None
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway,
                options={"require": ["iss", "sub", "aud", "exp", "iat", "jti"]},
            )
        except jwt.PyJWTError:
            return None
        return _principal_from_payload(payload)

    def _verification_key(self, kid: object) -> Any | None:
        jwks = self._load_jwks()
        keys = jwks.get("keys") if isinstance(jwks, dict) else None
        if not isinstance(keys, list) or not keys:
            return None
        if isinstance(kid, str):
            for key in keys:
                if isinstance(key, dict) and key.get("kid") == kid:
                    return _rsa_from_jwk(key)
            return None
        # Sin `kid`: solo aceptable si el JWKS publica una única clave.
        if len(keys) == 1 and isinstance(keys[0], dict):
            return _rsa_from_jwk(keys[0])
        return None

    def _load_jwks(self) -> dict[str, Any] | None:
        now = time.monotonic()
        if self._jwks_cache is not None and now - self._jwks_fetched_at < self._cache_ttl:
            return self._jwks_cache
        try:
            data = self._jwks_provider() if self._jwks_provider is not None else self._fetch()
        except Exception:  # noqa: BLE001 — JWKS no disponible ⇒ no se autentica (fail-closed)
            return self._jwks_cache
        if isinstance(data, dict):
            self._jwks_cache = data
            self._jwks_fetched_at = now
        return self._jwks_cache

    def _fetch(self) -> dict[str, Any]:
        response = requests.get(
            self._jwks_url, timeout=self._timeout, headers={"User-Agent": _BROWSER_UA}
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}


def _rsa_from_jwk(jwk: dict[str, Any]) -> Any:
    from jwt.algorithms import RSAAlgorithm

    return RSAAlgorithm.from_jwk(json.dumps(jwk))
