"""Almacén de resolución MySQL (F5.8)."""

from __future__ import annotations

import logging
from typing import cast

import pymysql
from pymysql.cursors import DictCursor

from .memory import _item_same, _j, _MemoryStore, _now

_LOGGER = logging.getLogger("osap.resolution")



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



