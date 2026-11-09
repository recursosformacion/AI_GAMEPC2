"""V1 — Proveedores de service token (SERVICE JWT).

``ClientCredentialsServiceTokenProvider`` obtiene un token de osap-auth vía OAuth2
``client_credentials``. ``StaticServiceTokenProvider`` entrega un token fijo (tests / dev).
Nunca representan un usuario.
"""

import json
import threading
import time
import urllib.request

from src.osap.ports.service_token import IServiceTokenProvider

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class ClientCredentialsServiceTokenProvider(IServiceTokenProvider):
    """Obtiene el service token de osap-auth mediante ``client_credentials``."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        timeout: int = 15,
        audience: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._timeout = timeout
        # Audiencia objetivo del service token. `None` = audiencia por defecto de osap-auth
        # (tokens para storage: `aud=osap-api`). Para consumir osap-support M2M hay que pedir
        # explícitamente `aud=osap-support`, que el receptor valida (`service_audience`).
        self._audience = audience
        # Cache por (scopes, audience). Sin cache, cada operación de storage pedía un
        # token nuevo: un pico de tráfico podía tumbar osap-auth y disparar un bucle de
        # reintentos con 429. El lock evita estampidas de peticiones concurrentes.
        self._lock = threading.Lock()
        self._cache: dict[tuple[tuple[str, ...], str | None], tuple[str, float]] = {}

    def token(self, scopes: tuple[str, ...]) -> str:
        key = (tuple(scopes), self._audience)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached[1] > now:
                return cached[0]
            token, expires_in = self._request_token(scopes)
            ttl = expires_in if expires_in > 0 else 300.0
            self._cache[key] = (token, time.monotonic() + max(5.0, ttl - 60.0))
            return token

    def _request_token(self, scopes: tuple[str, ...]) -> tuple[str, float]:
        body: dict[str, object] = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": " ".join(scopes),
        }
        if self._audience:
            body["audience"] = self._audience
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._token_url,
            data=payload,
            headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (auth token endpoint)
            doc = json.loads(response.read())
        token = doc.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("osap-auth did not return an access_token")
        raw_expires = doc.get("expires_in")
        expires_in = (
            float(raw_expires)
            if isinstance(raw_expires, (int, float)) and not isinstance(raw_expires, bool)
            else 0.0
        )
        return token, expires_in


class StaticServiceTokenProvider(IServiceTokenProvider):
    """Devuelve un token fijo (tests / dev), ignorando los scopes."""

    def __init__(self, token: str) -> None:
        self._token = token

    def token(self, scopes: tuple[str, ...]) -> str:
        return self._token
