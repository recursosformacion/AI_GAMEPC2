"""Base de datos operativa de osap-api (MySQL).

Aloja SOLO estado operativo del propio osap-api, nunca una copia del catálogo de
osap-storage. Contiene: sugerencias de fuentes/proveedores y su auditoría, proveedores
dinámicos + configuración de conectores, y configuración operativa persistente.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pymysql
from pymysql.cursors import DictCursor

_DB_PARAMS = ("host", "user", "password", "database")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class OpStore:
    """Almacén operativo de osap-api respaldado por MySQL."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        user: str = "osap2027",
        password: str = "2027osapdb",
        database: str = "osap-api",
    ) -> None:
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
            CREATE TABLE IF NOT EXISTS source_suggestions (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                type VARCHAR(64) NOT NULL,
                location VARCHAR(1024) NOT NULL,
                mapping TEXT NOT NULL,
                requested_by VARCHAR(255) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                admin_message TEXT,
                created_at VARCHAR(64) NOT NULL,
                decided_at VARCHAR(64),
                decided_by VARCHAR(255)
            )
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS providers (
                provider_id VARCHAR(128) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                kind VARCHAR(32) NOT NULL DEFAULT 'dynamic',
                base_url VARCHAR(1024),
                wired TINYINT NOT NULL DEFAULT 0,
                config TEXT NOT NULL,
                created_at VARCHAR(64) NOT NULL
            )
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS app_config (
                `key` VARCHAR(128) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at VARCHAR(64) NOT NULL
            )
            """
        )

    # --- sugerencias de fuentes ---------------------------------------------

    def list_suggestions(self) -> list[dict[str, object]]:
        return self._run("SELECT * FROM source_suggestions ORDER BY created_at")

    def add_suggestion(
        self,
        suggestion_id: str,
        name: str,
        source_type: str,
        location: str,
        mapping: dict[str, object],
        requested_by: str,
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO source_suggestions (id, name, type, location, mapping, "
            "requested_by, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)",
            (
                suggestion_id,
                name,
                source_type,
                location,
                json.dumps(mapping, ensure_ascii=False),
                requested_by,
                _now(),
            ),
        )
        row = self.get_suggestion(suggestion_id)
        assert row is not None
        return row

    def get_suggestion(self, suggestion_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM source_suggestions WHERE id = %s", (suggestion_id,))
        return rows[0] if rows else None

    def resolve_suggestion(
        self, suggestion_id: str, status: str, message: str, decided_by: str
    ) -> dict[str, object] | None:
        self._run(
            "UPDATE source_suggestions SET status = %s, admin_message = %s, "
            "decided_at = %s, decided_by = %s WHERE id = %s",
            (status, message, _now(), decided_by, suggestion_id),
        )
        return self.get_suggestion(suggestion_id)

    def pending_suggestion_count(self) -> int:
        rows = self._run("SELECT COUNT(*) AS n FROM source_suggestions WHERE status = 'pending'")
        return int(str(rows[0]["n"])) if rows else 0

    # --- proveedores dinámicos ----------------------------------------------

    def list_providers(self) -> list[dict[str, object]]:
        return self._run("SELECT * FROM providers ORDER BY name")

    def get_provider(self, provider_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM providers WHERE provider_id = %s", (provider_id,))
        return rows[0] if rows else None

    def upsert_provider(
        self,
        provider_id: str,
        name: str,
        base_url: str | None = None,
        wired: bool = False,
        kind: str = "dynamic",
        config: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = json.dumps(config or {}, ensure_ascii=False)
        self._run(
            "INSERT INTO providers (provider_id, name, kind, base_url, wired, config, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE name = VALUES(name), base_url = VALUES(base_url), "
            "wired = VALUES(wired), config = VALUES(config)",
            (provider_id, name, kind, base_url, int(wired), payload, _now()),
        )
        row = self.get_provider(provider_id)
        assert row is not None
        return row

    def set_provider_wired(self, provider_id: str, wired: bool) -> dict[str, object] | None:
        self._run("UPDATE providers SET wired = %s WHERE provider_id = %s", (int(wired), provider_id))
        return self.get_provider(provider_id)

    # --- configuración operativa --------------------------------------------

    def get_config(self, key: str) -> str | None:
        rows = self._run("SELECT value FROM app_config WHERE `key` = %s", (key,))
        return str(rows[0]["value"]) if rows else None

    def set_config(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO app_config (`key`, value, updated_at) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)",
            (key, value, _now()),
        )
