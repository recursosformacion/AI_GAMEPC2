"""Almacén de resolución en memoria + igualdad de items (F5.8)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import cast

_LOGGER = logging.getLogger("osap.resolution")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _j(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class _MemoryStore:
    """Almacén en memoria con la misma interfaz (fallback cuando MySQL no está)."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, object]] = {}
        self._provider_results: list[dict[str, object]] = []
        self._items: list[dict[str, object]] = []

    # --- sesiones ---

    def create_session(
        self,
        session_id: str,
        query_json: str,
        providers_json: str,
        policy_json: str,
        created_at: str,
        expires_at: str,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "session_id": session_id,
            "status": "acquiring",
            "query_json": query_json,
            "providers_json": providers_json,
            "policy_json": policy_json,
            "progress_json": "{}",
            "error": None,
            "selection_json": None,
            "created_at": created_at,
            "updated_at": created_at,
            "expires_at": expires_at,
        }
        self._sessions[session_id] = row
        return row

    def get_session(self, session_id: str) -> dict[str, object] | None:
        return self._sessions.get(session_id)

    def update_status(self, session_id: str, status: str, error: str | None = None) -> dict[str, object] | None:
        row = self._sessions.get(session_id)
        if row is None:
            return None
        row["status"] = status
        row["updated_at"] = _now()
        if error is not None:
            row["error"] = error
        return row

    def set_selection(self, session_id: str, selection_json: str) -> dict[str, object] | None:
        """Persiste la representación seleccionada (resultado normal, no error)."""
        row = self._sessions.get(session_id)
        if row is None:
            return None
        row["selection_json"] = selection_json
        row["updated_at"] = _now()
        return row

    def set_progress(self, session_id: str, progress_json: str) -> dict[str, object] | None:
        row = self._sessions.get(session_id)
        if row is None:
            return None
        row["progress_json"] = progress_json
        row["updated_at"] = _now()
        return row

    def touch(self, session_id: str) -> None:
        row = self._sessions.get(session_id)
        if row is not None:
            row["updated_at"] = _now()

    # --- resultados ---

    def list_results(self, session_id: str, offset: int, limit: int) -> tuple[list[dict[str, object]], int]:
        rows = [r for r in self._items if r["session_id"] == session_id]
        total = len(rows)
        return rows[offset : offset + limit], total

    # --- adquisición (provider_results) ---

    def add_provider_result(
        self,
        result_id: str,
        session_id: str,
        provider: str,
        pagination_kind: str,
        cursor_value: str,
        next_cursor: str | None,
        status: str,
        payload_json: str,
        meta_json: str,
        acquired_at: str,
    ) -> dict[str, object]:
        for existing in self._provider_results:
            if (
                existing["session_id"] == session_id
                and existing["provider"] == provider
                and existing["cursor_value"] == cursor_value
            ):
                return existing
        row: dict[str, object] = {
            "id": result_id,
            "session_id": session_id,
            "provider": provider,
            "pagination_kind": pagination_kind,
            "cursor_value": cursor_value,
            "next_cursor": next_cursor,
            "status": status,
            "payload_json": payload_json,
            "meta_json": meta_json,
            "acquired_at": acquired_at,
        }
        self._provider_results.append(row)
        return row

    def list_provider_results(self, session_id: str, provider: str) -> list[dict[str, object]]:
        return [r for r in self._provider_results if r["session_id"] == session_id and r["provider"] == provider]

    def list_all_provider_results(self, session_id: str) -> list[dict[str, object]]:
        return [
            r
            for r in self._provider_results
            if r["session_id"] == session_id and r["status"] in ("fetched", "end_of_provider")
        ]

    def last_provider_result(self, session_id: str, provider: str) -> dict[str, object] | None:
        rows = self.list_provider_results(session_id, provider)
        return rows[-1] if rows else None

    def list_acquiring_sessions(self) -> list[dict[str, object]]:
        return [r for r in self._sessions.values() if r.get("status") == "acquiring"]

    def delete_session_data(self, session_id: str) -> None:
        """Elimina provider_results y resolution_items de la sesión (TTL). La fila de la
        sesión se conserva (para que GET /sessions devuelva `expired`)."""
        self._provider_results = [r for r in self._provider_results if r["session_id"] != session_id]
        self._items = [r for r in self._items if r["session_id"] != session_id]

    # --- items (matching provisional) ---

    def get_item(self, session_id: str, item_id: str) -> dict[str, object] | None:
        for r in self._items:
            if r["session_id"] == session_id and r["id"] == item_id:
                return r
        return None

    def replace_items(self, session_id: str, items: list[dict[str, object]], stage: str) -> int:
        """Upserta los items y borra los que ya no aplican. Solo sube `revision` cuando
        el contenido cambia (idempotente: el mismo universo → mismo resultado)."""
        incoming: set[str] = set()
        changed = 0
        for it in items:
            item_id = str(it["id"])
            incoming.add(item_id)
            existing = self.get_item(session_id, item_id)
            if existing is not None and str(existing.get("resolution_stage")) == stage and _item_same(existing, it):
                continue
            revision = int(cast("int", existing["revision"])) + 1 if existing is not None else 1
            row: dict[str, object] = {
                "id": item_id,
                "session_id": session_id,
                "ref_json": _j(it.get("ref") or {}),
                "status": str(it["status"]),
                "resolution_stage": stage,
                "revision": revision,
                "normalized_json": _j(it.get("normalized") or {}),
                "resolved_json": _j(it.get("resolved") or {}),
                "confidence": float(cast("float", it.get("confidence") or 0.0)),
                "candidates_json": _j(it.get("candidates") or []),
                "evidence_json": _j(it.get("evidence") or []),
                "updated_at": _now(),
            }
            if existing is not None:
                self._items = [
                    r if not (r["session_id"] == session_id and r["id"] == item_id) else row for r in self._items
                ]
            else:
                self._items.append(row)
            changed += 1
        self._items = [
            r for r in self._items if not (r["session_id"] == session_id and r["id"] not in incoming)
        ]
        return changed




def _item_same(row: dict[str, object], it: dict[str, object]) -> bool:
    """True si el item persistido ya tiene el mismo contenido (idempotencia de revision)."""
    return (
        str(row.get("status")) == str(it["status"])
        and _json_eq(row.get("normalized_json"), it.get("normalized"))
        and _json_eq(row.get("resolved_json"), it.get("resolved"))
        and float(cast("float", row.get("confidence") or 0.0)) == float(cast("float", it.get("confidence") or 0.0))
        and _json_eq(row.get("candidates_json"), it.get("candidates"))
        and _json_eq(row.get("evidence_json"), it.get("evidence"))
    )


def _json_eq(raw: object, value: object) -> bool:
    try:
        return bool(json.loads(str(raw or "null") if raw else "null") == value)
    except ValueError:
        return False



