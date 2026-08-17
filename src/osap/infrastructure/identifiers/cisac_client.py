"""Cliente CISAC ISWC/IPI — preparado, inactivo sin credenciales.

CISAC ofrece (Dec 2025):
  * ISWC IPI Context Search — nombre de creador + títulos de obra → IPI del creador.
  * ISWC Database REST API (Azure API Management) — lookup de obra por ISWC.
  * ISWC Open Data — licencia royalty-free de acceso a datos.

Este cliente queda listo y se activa al configurar `base_url` + `api_key`. Mientras no
haya credenciales, `available` es False y los métodos devuelven vacío (no se golpea nada).
"""

from __future__ import annotations

import json
import urllib.request

_USER_AGENT = "osap-identifiers/0.1 (reconstruction; read-only)"


class CisacClient:
    def __init__(self, base_url: str = "", api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._timeout = 30

    @property
    def available(self) -> bool:
        return bool(self._base_url and self._api_key)

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        if self._api_key:
            headers["Ocp-Apim-Subscription-Key"] = self._api_key
        return headers

    def ipi_context_search(self, creator_name: str, work_titles: list[str]) -> list[dict[str, object]]:
        """Nombre de creador + títulos de obra → candidatos IPI.

        Endpoint y payload según especificación CISAC ISWC IPI Context Search (pendiente
        de confirmar con las credenciales). Devuelve [] sin credenciales o ante error.
        """
        if not self.available or not creator_name:
            return []
        payload = json.dumps(
            {"creator": {"name": creator_name}, "works": [{"title": t} for t in work_titles]}
        ).encode("utf-8")
        try:
            request = urllib.request.Request(
                f"{self._base_url}/ipi-context-search",
                data=payload,
                headers={**self._headers(), "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (B2B API)
                doc = json.loads(response.read())
            results = doc.get("results") if isinstance(doc, dict) else doc
            if isinstance(results, list):
                return [dict(r) for r in results if isinstance(r, dict)]
            return []
        except Exception:  # noqa: BLE001
            return []

    def lookup_work(self, iswc: str) -> dict[str, object] | None:
        """Lookup de una obra por ISWC en la ISWC Database REST API."""
        if not self.available or not iswc:
            return None
        try:
            import urllib.parse

            request = urllib.request.Request(
                f"{self._base_url}/works?iswc={urllib.parse.quote(iswc)}",
                headers=self._headers(),
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (B2B API)
                doc = json.loads(response.read())
            return dict(doc) if isinstance(doc, dict) else None
        except Exception:  # noqa: BLE001
            return None
