"""Cliente de la API interna de ai_noticias.

OSAP es el propietario de la identidad y del consentimiento. Este cliente solo envía
`language` y `topics`; nunca usuarios, correos ni listas de destinatarios. La API de
ai_noticias devuelve el corpus ya filtrado.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class NewsUnavailableError(RuntimeError):
    """ai_noticias no respondió o rechazó la credencial de servicio."""


class NewsClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8401",
        token: str | None = None,
        timeout: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._token)

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise NewsUnavailableError("servicio de noticias sin token configurado")
        return {
            "Accept": "application/json",
            "X-OSAP-News-Token": self._token,
        }

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, object]:
        url = self._base_url + path
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise NewsUnavailableError("credencial de noticias rechazada") from exc
            raise NewsUnavailableError(f"ai_noticias devolvió HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise NewsUnavailableError(f"ai_noticias no disponible: {exc}") from exc
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise NewsUnavailableError("ai_noticias no devolvió JSON válido") from exc
        if not isinstance(data, dict):
            raise NewsUnavailableError("respuesta de ai_noticias inválida")
        return data

    def topics(self) -> list[dict[str, object]]:
        data = self._get("/api/v1/news/topics")
        items = data.get("items")
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    def query(
        self,
        *,
        languages: list[str],
        topics: list[str],
        limit: int = 20,
        days: int = 30,
    ) -> dict[str, object]:
        params = {
            "languages": ",".join(languages),
            "topics": ",".join(topics),
            "limit": str(max(1, min(limit, 100))),
            "days": str(max(1, min(days, 3650))),
        }
        return self._get("/api/v1/news", params)

