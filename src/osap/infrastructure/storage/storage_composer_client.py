"""V1 — Cliente de compositores vía el contrato de osap-storage.

osap-api no inventa contratos: usa los endpoints administrativos existentes de
osap-storage (`/api/admin/composers*`) como backend. Consulta con scope ``storage:read``;
fusión con ``storage:admin``. Solo osap-api se autentica como SERVICE; nunca se reenvía el
JWT del usuario.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from src.osap.ports.service_token import IServiceTokenProvider

_LOGGER = logging.getLogger("osap.storage")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class StorageComposerError(Exception):
    """osap-storage no respondió correctamente a una operación de compositores."""


class StorageComposerClient:
    """Cliente de los endpoints de compositores de osap-storage (HTTP).

    Consulta usa el token de servicio normal (``storage:read``). La fusión usa un
    proveedor de token **administrativo** separado (``storage:admin``); nunca se concede
    ``storage:admin`` al cliente normal de osap-api.
    """

    def __init__(
        self,
        base_url: str = "https://storage.openmusicrepository.com",
        timeout: int = 15,
        token_provider: IServiceTokenProvider | None = None,
        admin_token_provider: IServiceTokenProvider | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token_provider = token_provider
        self._admin_token_provider = admin_token_provider

    def list_composers(
        self, q: str | None, limit: int, offset: int, review: str | None = None
    ) -> dict[str, object]:
        query = {"limit": str(limit), "offset": str(offset)}
        if q:
            query["q"] = q
        if review:
            query["review"] = review
        path = f"/api/admin/composers?{urllib.parse.urlencode(query)}"
        status, doc = self._call("GET", path, scope="storage:read")
        if 200 <= status < 300 and isinstance(doc, dict):
            return doc
        return {"items": [], "total": 0}

    def get_composer(self, composer_id: str) -> dict[str, object] | None:
        status, doc = self._call("GET", f"/api/admin/composers/{_q(composer_id)}", scope="storage:read")
        if 200 <= status < 300 and isinstance(doc, dict):
            return doc
        return None

    def composer_works(self, composer_id: str, limit: int, offset: int) -> dict[str, object]:
        path = f"/api/admin/composers/{_q(composer_id)}/works?limit={limit}&offset={offset}"
        status, doc = self._call("GET", path, scope="storage:read")
        if not 200 <= status < 300 or not isinstance(doc, dict):
            return {"items": [], "total": 0}
        items = doc.get("items")
        enriched: list[dict[str, object]] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry["tags"] = self._work_tags(_as_int(item.get("work_id")))
            enriched.append(entry)
        return {"items": enriched, "total": _as_int(doc.get("total"))}

    def _work_tags(self, work_id: int) -> str | None:
        status, doc = self._call("GET", f"/api/v1/works/{_q(str(work_id))}", scope="storage:read")
        if 200 <= status < 300 and isinstance(doc, dict):
            work = doc.get("work")
            if isinstance(work, dict):
                tags = work.get("tags")
                return _as_str(tags) or None
        return None

    def get_work(self, work_id: str) -> dict[str, object] | None:
        """Devuelve el detalle completo de una obra (work + resources) para inspección."""
        status, doc = self._call("GET", f"/api/v1/works/{_q(work_id)}", scope="storage:read")
        if 200 <= status < 300 and isinstance(doc, dict):
            return doc
        return None

    def merge_composers(self, target_id: str, source_ids: list[str]) -> tuple[int, dict[str, object]]:
        payload: dict[str, object] = {"source_ids": source_ids}
        status, doc = self._call(
            "POST",
            f"/api/admin/composers/{_q(target_id)}/merge",
            payload=payload,
            scope="storage:admin",
            provider=self._admin_token_provider,
        )
        if 200 <= status < 300 and isinstance(doc, dict):
            return status, doc
        return status, {}

    def create_composer(self, name: str) -> dict[str, object] | None:
        payload: dict[str, object] = {"name": name}
        status, doc = self._call(
            "POST",
            "/api/admin/composers",
            payload=payload,
            scope="storage:admin",
            provider=self._admin_token_provider,
        )
        if 200 <= status < 300 and isinstance(doc, dict):
            return doc
        return None

    def review_composer(self, composer_id: str, review_status: str) -> tuple[int, dict[str, object]]:
        payload: dict[str, object] = {"review_status": review_status}
        status, doc = self._call(
            "POST",
            f"/api/admin/composers/{_q(composer_id)}/review",
            payload=payload,
            scope="storage:admin",
            provider=self._admin_token_provider,
        )
        if 200 <= status < 300 and isinstance(doc, dict):
            return status, doc
        return status, {}

    def composer_review_stats(self) -> dict[str, int]:
        status, doc = self._call(
            "GET",
            "/api/admin/composers/stats",
            scope="storage:read",
            provider=self._token_provider,
        )
        if 200 <= status < 300 and isinstance(doc, dict):
            return {str(k): int(v) for k, v in doc.items()}
        return {"total": 0, "correct": 0, "incorrect": 0, "reviewed": 0, "not_reviewed": 0}

    def catalogues(self, prefix: str | None = None, composer: str | None = None) -> list[dict[str, object]]:
        query = {}
        if prefix:
            query["prefix"] = prefix
        if composer:
            query["composer"] = composer
        suffix = f"?{urllib.parse.urlencode(query)}" if query else ""
        status, doc = self._call(
            "GET",
            f"/api/v1/catalogues{suffix}",
            scope="storage:read",
            provider=self._token_provider,
        )
        if 200 <= status < 300 and isinstance(doc, list):
            return [d for d in doc if isinstance(d, dict)]
        return []

    # -- helpers -------------------------------------------------------------

    def _call(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        scope: str = "storage:read",
        provider: IServiceTokenProvider | None = None,
    ) -> tuple[int, object]:
        url = self._base_url + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers: dict[str, str] = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        effective = provider if provider is not None else self._token_provider
        if effective is not None:
            try:
                headers["Authorization"] = f"Bearer {effective.token((scope,))}"
            except Exception as exc:  # noqa: BLE001
                # Si no se puede obtener el token (p. ej. dev contra storage remoto sin
                # auth accesible), se llama a storage sin autenticación: sus endpoints de
                # lectura son públicos y así el modo desarrollo puede leer.
                _LOGGER.warning("No hay token de servicio %s; llamando a storage sin auth: %s", scope, exc)
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 (storage contract)
                raw = response.read()
                try:
                    doc: object = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    doc = {}
                return response.status, doc
        except urllib.error.HTTPError as exc:
            return exc.code, {}
        except Exception as exc:
            raise StorageComposerError(str(exc)) from exc


def _q(value: str) -> str:
    return urllib.parse.quote(value)


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _as_str(value: object) -> str:
    return str(value) if value is not None else ""
