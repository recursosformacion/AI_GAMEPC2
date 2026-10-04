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
        # El detalle de representación expone `works_id` (fallback `work_id`).
        work_id = doc.get("works_id")
        if work_id is None:
            work_id = doc.get("work_id")
        return int(work_id) if work_id is not None else None

    def create_resource(
        self,
        *,
        work_id: int,
        representation_id: int,
        resource_type: str,
        name: str,
        status: str,
        file_id: int,
    ) -> dict[str, object]:
        """Materializa el recurso en el catálogo de storage (`POST /api/admin/resources`).

        Crear la fila `works_resources` es lo que hace el recurso **servable** (`/api/download/{id}`).
        """
        payload = json.dumps(
            {
                "work_id": work_id,
                "representation_id": representation_id,
                "type": resource_type,
                "name": name,
                "status": status,
                "file_id": file_id,
            }
        ).encode()
        status_code, doc = self._request(
            "POST",
            "/api/admin/resources",
            payload,
            "storage:admin",
            self._admin_token_provider,
            content_type="application/json",
        )
        if not (200 <= status_code < 300) or not isinstance(doc, dict):
            raise StorageContributionError(f"storage create_resource HTTP {status_code}")
        return doc

    def work_exists(self, work_id: str) -> bool:
        wid = urllib.parse.quote(str(work_id), safe="")
        status, _doc = self._request(
            "GET", f"/api/admin/works/{wid}", None, "storage:admin", self._admin_token_provider
        )
        if status == 404:
            return False
        if 200 <= status < 300:
            return True
        raise StorageContributionError(f"storage work HTTP {status}")

    def create_work(
        self,
        *,
        title: str,
        origin: str,
        origin_id: str | None = None,
        license: str | None = None,
        song_name: str | None = None,
        attribution_type: str | None = None,
    ) -> int:
        payload: dict[str, object] = {"title": title, "origin": origin}
        for key, value in (
            ("origin_id", origin_id),
            ("license", license),
            ("song_name", song_name),
            ("attribution_type", attribution_type),
        ):
            if value:
                payload[key] = value
        status, doc = self._request(
            "POST", "/api/admin/works", json.dumps(payload).encode(), "storage:admin",
            self._admin_token_provider, content_type="application/json",
        )
        if not (200 <= status < 300) or not isinstance(doc, dict) or doc.get("id") is None:
            raise StorageContributionError(f"storage create_work HTTP {status}")
        return int(str(doc["id"]))

    def create_representation(
        self,
        *,
        works_id: int,
        origin: str,
        rep_type: str,
        license: str | None = None,
        source_name: str | None = None,
        origin_id: str | None = None,
    ) -> int:
        payload: dict[str, object] = {"works_id": works_id, "origin": origin, "type": rep_type}
        for key, value in (("license", license), ("source_name", source_name), ("origin_id", origin_id)):
            if value:
                payload[key] = value
        status, doc = self._request(
            "POST", "/api/admin/representations", json.dumps(payload).encode(), "storage:admin",
            self._admin_token_provider, content_type="application/json",
        )
        if not (200 <= status < 300) or not isinstance(doc, dict) or doc.get("id") is None:
            raise StorageContributionError(f"storage create_representation HTTP {status}")
        return int(str(doc["id"]))

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
        content_type: str = "application/octet-stream",
    ) -> tuple[int, object]:
        token = provider.token((scope,)) if provider is not None else ""
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": content_type,
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
