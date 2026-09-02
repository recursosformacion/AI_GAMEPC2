"""Almacén de sesiones de resolución de osap-api (OpStore).

Misma base de datos operativa que `op_store` (MySQL con fallback a memoria), pero para el
modelo de resolución del ADR-0033 / resolution-store-v1: `resolution_sessions`,
`provider_results` y `resolution_items`. Contiene SOLO estado operativo de una operación
de resolución concreta; nunca una copia del catálogo de osap-storage.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import cast

import pymysql
from pymysql.cursors import DictCursor

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


class _MysqlStore(_MemoryStore):
    """Almacén de resolución respaldado por MySQL."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        self._params = {"host": host, "user": user, "password": password, "database": database}
        self._init()

    def _conn(self) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=self._params["host"],
            user=self._params["user"],
            password=self._params["password"],
            database=self._params["database"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )

    def _run(self, sql: str, args: tuple[object, ...] | None = None) -> list[dict[str, object]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                if cur.description:
                    return [dict(row) for row in cur.fetchall()]
                return []
        finally:
            conn.close()

    def _init(self) -> None:
        self._run(
            """
            CREATE TABLE IF NOT EXISTS resolution_sessions (
                session_id      VARCHAR(64)  PRIMARY KEY,
                status          VARCHAR(32)  NOT NULL DEFAULT 'acquiring',
                query_json      TEXT         NOT NULL,
                providers_json  TEXT         NOT NULL,
                policy_json     TEXT         NOT NULL,
                progress_json   TEXT         NOT NULL,
                error           TEXT,
                selection_json  TEXT,
                created_at      VARCHAR(64)  NOT NULL,
                updated_at      VARCHAR(64)  NOT NULL,
                expires_at      VARCHAR(64)  NOT NULL,
                INDEX idx_rs_status  (status),
                INDEX idx_rs_updated (updated_at)
            )
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS provider_results (
                id              VARCHAR(64)  PRIMARY KEY,
                session_id      VARCHAR(64)  NOT NULL,
                provider        VARCHAR(64)  NOT NULL,
                pagination_kind VARCHAR(16)  NOT NULL,
                cursor_value    VARCHAR(512) NOT NULL,
                next_cursor     VARCHAR(512),
                status          VARCHAR(32)  NOT NULL DEFAULT 'fetched',
                payload_json    MEDIUMTEXT,
                meta_json       TEXT,
                acquired_at     VARCHAR(64)  NOT NULL,
                UNIQUE KEY uq_pr_cursor (session_id, provider, cursor_value),
                INDEX idx_pr_session (session_id)
            )
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS resolution_items (
                id               VARCHAR(64)  PRIMARY KEY,
                session_id       VARCHAR(64)  NOT NULL,
                ref_json         TEXT         NOT NULL,
                status           VARCHAR(32)  NOT NULL,
                resolution_stage VARCHAR(16)  NOT NULL DEFAULT 'provisional',
                revision         INT          NOT NULL DEFAULT 1,
                normalized_json  TEXT,
                resolved_json    TEXT,
                confidence       DECIMAL(6,5) NOT NULL DEFAULT 0,
                candidates_json  TEXT,
                evidence_json    TEXT,
                updated_at       VARCHAR(64)  NOT NULL,
                INDEX idx_ri_session (session_id),
                INDEX idx_ri_status  (status)
            )
            """
        )
        # Migración idempotente: columna selection_json para sesiones ya creadas.
        cols = self._run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'resolution_sessions' "
            "AND column_name = 'selection_json'"
        )
        if not cols:
            try:
                self._run("ALTER TABLE resolution_sessions ADD COLUMN selection_json TEXT")
            except pymysql.err.OperationalError:
                _LOGGER.warning("no se pudo añadir selection_json (tabla en uso o permisos)")

    def create_session(
        self,
        session_id: str,
        query_json: str,
        providers_json: str,
        policy_json: str,
        created_at: str,
        expires_at: str,
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO resolution_sessions (session_id, status, query_json, providers_json, "
            "policy_json, progress_json, created_at, updated_at, expires_at) "
            "VALUES (%s, 'acquiring', %s, %s, %s, '{}', %s, %s, %s)",
            (session_id, query_json, providers_json, policy_json, created_at, created_at, expires_at),
        )
        row = self.get_session(session_id)
        assert row is not None
        return row

    def get_session(self, session_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM resolution_sessions WHERE session_id = %s", (session_id,))
        return rows[0] if rows else None

    def update_status(self, session_id: str, status: str, error: str | None = None) -> dict[str, object] | None:
        if error is not None:
            self._run(
                "UPDATE resolution_sessions SET status = %s, error = %s, updated_at = %s WHERE session_id = %s",
                (status, error, _now(), session_id),
            )
        else:
            self._run(
                "UPDATE resolution_sessions SET status = %s, updated_at = %s WHERE session_id = %s",
                (status, _now(), session_id),
            )
        return self.get_session(session_id)

    def set_selection(self, session_id: str, selection_json: str) -> dict[str, object] | None:
        """Persiste la representación seleccionada (resultado normal, no error)."""
        self._run(
            "UPDATE resolution_sessions SET selection_json = %s, updated_at = %s WHERE session_id = %s",
            (selection_json, _now(), session_id),
        )
        return self.get_session(session_id)

    def set_progress(self, session_id: str, progress_json: str) -> dict[str, object] | None:
        self._run(
            "UPDATE resolution_sessions SET progress_json = %s, updated_at = %s WHERE session_id = %s",
            (progress_json, _now(), session_id),
        )
        return self.get_session(session_id)

    def touch(self, session_id: str) -> None:
        self._run("UPDATE resolution_sessions SET updated_at = %s WHERE session_id = %s", (_now(), session_id))

    def list_results(self, session_id: str, offset: int, limit: int) -> tuple[list[dict[str, object]], int]:
        total_rows = self._run("SELECT COUNT(*) AS n FROM resolution_items WHERE session_id = %s", (session_id,))
        total = int(str(total_rows[0]["n"])) if total_rows else 0
        rows = self._run(
            "SELECT * FROM resolution_items WHERE session_id = %s ORDER BY id LIMIT %s OFFSET %s",
            (session_id, int(limit), int(offset)),
        )
        return rows, total

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
        self._run(
            "INSERT INTO provider_results (id, session_id, provider, pagination_kind, cursor_value, "
            "next_cursor, status, payload_json, meta_json, acquired_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE id = id",
            (
                result_id,
                session_id,
                provider,
                pagination_kind,
                cursor_value,
                next_cursor,
                status,
                payload_json,
                meta_json,
                acquired_at,
            ),
        )
        return self.last_provider_result(session_id, provider) or {
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

    def list_provider_results(self, session_id: str, provider: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM provider_results WHERE session_id = %s AND provider = %s ORDER BY acquired_at",
            (session_id, provider),
        )

    def last_provider_result(self, session_id: str, provider: str) -> dict[str, object] | None:
        rows = self._run(
            "SELECT * FROM provider_results WHERE session_id = %s AND provider = %s "
            "ORDER BY acquired_at DESC LIMIT 1",
            (session_id, provider),
        )
        return rows[0] if rows else None

    def list_all_provider_results(self, session_id: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM provider_results WHERE session_id = %s "
            "AND status IN ('fetched', 'end_of_provider') ORDER BY acquired_at",
            (session_id,),
        )

    def list_acquiring_sessions(self) -> list[dict[str, object]]:
        return self._run("SELECT * FROM resolution_sessions WHERE status = 'acquiring' ORDER BY created_at")

    def delete_session_data(self, session_id: str) -> None:
        self._run("DELETE FROM provider_results WHERE session_id = %s", (session_id,))
        self._run("DELETE FROM resolution_items WHERE session_id = %s", (session_id,))

    def get_item(self, session_id: str, item_id: str) -> dict[str, object] | None:
        rows = self._run(
            "SELECT * FROM resolution_items WHERE session_id = %s AND id = %s", (session_id, item_id)
        )
        return rows[0] if rows else None

    def replace_items(self, session_id: str, items: list[dict[str, object]], stage: str) -> int:
        incoming: list[str] = []
        changed = 0
        for it in items:
            item_id = str(it["id"])
            incoming.append(item_id)
            existing = self.get_item(session_id, item_id)
            if existing is not None and str(existing.get("resolution_stage")) == stage and _item_same(existing, it):
                continue
            revision = int(cast("int", existing["revision"])) + 1 if existing is not None else 1
            self._run(
                "INSERT INTO resolution_items (id, session_id, ref_json, status, resolution_stage, "
                "revision, normalized_json, resolved_json, confidence, candidates_json, evidence_json, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE ref_json = VALUES(ref_json), status = VALUES(status), "
                "resolution_stage = VALUES(resolution_stage), revision = VALUES(revision), "
                "normalized_json = VALUES(normalized_json), resolved_json = VALUES(resolved_json), "
                "confidence = VALUES(confidence), candidates_json = VALUES(candidates_json), "
                "evidence_json = VALUES(evidence_json), updated_at = VALUES(updated_at)",
                (
                    item_id,
                    session_id,
                    _j(it.get("ref") or {}),
                    str(it["status"]),
                    stage,
                    revision,
                    _j(it.get("normalized") or {}),
                    _j(it.get("resolved") or {}),
                    float(cast("float", it.get("confidence") or 0.0)),
                    _j(it.get("candidates") or []),
                    _j(it.get("evidence") or []),
                    _now(),
                ),
            )
            changed += 1
        if incoming:
            placeholders = ", ".join(["%s"] * len(incoming))
            self._run(
                f"DELETE FROM resolution_items WHERE session_id = %s AND id NOT IN ({placeholders})",
                (session_id, *incoming),
            )
        else:
            self._run("DELETE FROM resolution_items WHERE session_id = %s", (session_id,))
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


def build_resolution_store(
    host: str = "127.0.0.1",
    user: str = "osap2027",
    password: str = "2027osapdb",
    database: str = "osap-api",
) -> _MemoryStore:
    """Factoría: MySQL con fallback a memoria si no está disponible."""
    params = {"host": host, "user": user, "password": password, "database": database}
    try:
        store = _MysqlStore(**params)
        store._init()
        return store
    except pymysql.err.OperationalError as exc:
        _LOGGER.warning("MySQL de resolución no disponible (%s); usando almacén en memoria", exc)
        return _MemoryStore()
