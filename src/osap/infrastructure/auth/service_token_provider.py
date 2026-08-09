"""V1 — Proveedores de service token (SERVICE JWT).

``ClientCredentialsServiceTokenProvider`` obtiene un token de osap-auth vía OAuth2
``client_credentials``. ``StaticServiceTokenProvider`` entrega un token fijo (tests / dev).
Nunca representan un usuario.
"""

import json
import urllib.parse
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
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._timeout = timeout

    def token(self, scopes: tuple[str, ...]) -> str:
        data = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": " ".join(scopes),
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self._token_url,
            data=data,
            headers={"User-Agent": _USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (auth token endpoint)
            doc = json.loads(response.read())
        token = doc.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("osap-auth did not return an access_token")
        return token


class StaticServiceTokenProvider(IServiceTokenProvider):
    """Devuelve un token fijo (tests / dev), ignorando los scopes."""

    def __init__(self, token: str) -> None:
        self._token = token

    def token(self, scopes: tuple[str, ...]) -> str:
        return self._token
