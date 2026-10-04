"""Cliente de osap-api hacia osap-storage para aportaciones (upload + resolución).

Reutiliza la interfaz existente de storage, sin inventar contratos:
- `GET /api/admin/representations/{id}` (scope `storage:admin`) → `work_id` de la representación.
- `POST /api/v1/files/upload` (scope `storage:write`) → sube bytes y devuelve `File` (id, sha256…).

El fichero subido queda **no público** en storage; aquí no se crea `works_resources`.
osap-api usa un service token propio; nunca reenvía el JWT del usuario.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.osap.ports.service_token import IServiceTokenProvider

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class StorageContributionError(Exception):
    """osap-storage no respondió correctamente a una operación de aportación."""


class StorageContributionClient:
    def __init__(
        self,
        *,
        base_url: str = "https://storage.openmusicrepository.com",
        write_token_provider: IServiceTokenProvider | None = None,
        admin_token_provider: IServiceTokenProvider | None = None,
        timeout: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._write_token_provider = write_token_provider
        self._admin_token_provider = admin_token_provider
        self._timeout = timeout

    def representation_work_id(self, representation_id: str) -> int | None:
        """`work_id` de la representación, o `None` si no existe."""
        rid = urllib.parse.quote(str(representation_id), safe="")
        status, doc = self._request(
            "GET",
            f"/api/admin/representations/{rid}",
            None,
            "storage:admin",
            self._admin_token_provider,
        )
        if status == 404:
            return None
        if not (200 <= status < 300) or not isinstance(doc, dict):
            raise StorageContributionError(f"storage representación HTTP {status}")
        work_id = doc.get("work_id")
        return int(work_id) if work_id is not None else None

    def upload_file(self, *, name: str, mime_type: str | None, data: bytes) -> dict[str, object]:
        """Sube bytes a storage (no público) y devuelve el `File` (id, sha256, …)."""
        query: dict[str, str] = {"name": name}
        if mime_type:
            query["mime_type"] = mime_type
        qs = urllib.parse.urlencode(query)
        status, doc = self._request(
            "POST",
            f"/api/v1/files/upload?{qs}",
            data,
            "storage:write",
            self._write_token_provider,
        )
        if not (200 <= status < 300) or not isinstance(doc, dict):
            raise StorageContributionError(f"storage upload HTTP {status}")
        return doc

    # --- interno -------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: bytes | None,
        scope: str,
        provider: IServiceTokenProvider | None,
    ) -> tuple[int, object]:
        token = provider.token((scope,)) if provider is not None else ""
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "User-Agent": _USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            try:
                payload = exc.read()
                return exc.code, (json.loads(payload) if payload else None)
            except Exception:  # noqa: BLE001
                return exc.code, None
        except Exception as exc:  # noqa: BLE001 — red/servicio caído
            raise StorageContributionError(str(exc)) from exc
