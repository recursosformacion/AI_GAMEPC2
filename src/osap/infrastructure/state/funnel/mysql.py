"""Eventos del funnel respaldados por MySQL (BD de osap-api). Append-only."""

from __future__ import annotations

import json

import pymysql
from pymysql.cursors import DictCursor

from .memory import FunnelEvent, FunnelStage, MemoryStore, _value

_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS funnel_events (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        created_at DATETIME(6) NOT NULL,
        day CHAR(10) NOT NULL,
        event VARCHAR(32) NOT NULL,
        stage VARCHAR(8) NULL,
        user_id VARCHAR(64) NULL,
        ip_address VARCHAR(45) NULL,
        override_id BIGINT UNSIGNED NULL,
        detail JSON NULL,
        PRIMARY KEY (id),
        KEY idx_funnel_day (day),
        KEY idx_funnel_event_day (event, day),
        KEY idx_funnel_user (user_id, day)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
)


class _MysqlStore(MemoryStore):
    """Append-only en MySQL: solo INSERT (no hay UPDATE/DELETE en esta clase)."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        super().__init__()
        self._params = {"host": host, "user": user, "password": password, "database": database}
        self._run(_DDL[0])

    def _conn(self, *, autocommit: bool = True) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=self._params["host"],
            user=self._params["user"],
            password=self._params["password"],
            database=self._params["database"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=autocommit,
            ssl_disabled=str(self._params["host"]) in ("127.0.0.1", "localhost"),
        )

    def _run(self, sql: str, args: tuple[object, ...] | None = None) -> list[dict[str, object]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [dict(row) for row in cur.fetchall()] if cur.description else []
        finally:
            conn.close()

    def record_event(
        self,
        event: FunnelEvent,
        *,
        stage: FunnelStage | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
        override_id: int | None = None,
        detail: dict[str, object] | None = None,
        day: str | None = None,
    ) -> dict[str, object]:
        from .memory import today

        resolved_day = day or today()
        self._run(
            "INSERT INTO funnel_events (created_at, day, event, stage, user_id, ip_address, "
            "override_id, detail) VALUES (NOW(6), %s, %s, %s, %s, %s, %s, %s)",
            (
                resolved_day,
                _value(event),
                _value(stage),
                user_id,
                ip_address,
                override_id,
                json.dumps(detail, ensure_ascii=False) if detail else None,
            ),
        )
        return {
            "event": _value(event),
            "stage": _value(stage),
            "user_id": user_id,
            "ip_address": ip_address,
            "override_id": override_id,
            "detail": detail,
            "day": resolved_day,
        }

    def count(self, event: FunnelEvent | None = None, day: str | None = None) -> int:
        clauses: list[str] = []
        args: list[object] = []
        if event is not None:
            clauses.append("event = %s")
            args.append(_value(event))
        if day is not None:
            clauses.append("day = %s")
            args.append(day)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._run(f"SELECT COUNT(*) AS n FROM funnel_events{where}", tuple(args))
        return int(str(rows[0]["n"])) if rows else 0

    def query_events(self, from_day: str, to_day: str) -> list[dict[str, object]]:
        # Solo lectura y sin `ip_address` (privacidad: las métricas no exponen IPs).
        return self._run(
            "SELECT event, stage, user_id, day FROM funnel_events "
            "WHERE day BETWEEN %s AND %s ORDER BY id",
            (from_day, to_day),
        )

    def reverted_periods(self, user_id: str) -> set[str]:
        rows = self._run(
            "SELECT detail FROM funnel_events WHERE user_id = %s AND event = %s",
            (user_id, FunnelEvent.PROMOTION_REVERTED.value),
        )
        out: set[str] = set()
        for row in rows:
            detail = row.get("detail")
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except ValueError:
                    detail = None
            if isinstance(detail, dict) and detail.get("valid_from"):
                out.add(str(detail["valid_from"])[:10])
        return out

    def has_event(self, user_id: str, event: FunnelEvent) -> bool:
        rows = self._run(
            "SELECT 1 AS x FROM funnel_events WHERE user_id = %s AND event = %s LIMIT 1",
            (user_id, _value(event)),
        )
        return bool(rows)

    def events_for_user(self, user_id: str, day: str | None = None) -> list[dict[str, object]]:
        if day is None:
            return self._run(
                "SELECT event, stage, user_id, ip_address, override_id, day "
                "FROM funnel_events WHERE user_id = %s ORDER BY id",
                (user_id,),
            )
        return self._run(
            "SELECT event, stage, user_id, ip_address, override_id, day "
            "FROM funnel_events WHERE user_id = %s AND day = %s ORDER BY id",
            (user_id, day),
        )
