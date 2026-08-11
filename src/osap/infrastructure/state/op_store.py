"""Base de datos operativa de osap-api (SQLite).

Aloja SOLO estado operativo del propio osap-api, nunca una copia del catálogo de
osap-storage. Contiene: sugerencias de fuentes/proveedores y su auditoría, proveedores
dinámicos + configuración de conectores, y configuración operativa persistente.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    # sqlite3.Row itera los VALORES, no las claves: hay que usar .keys().
    return {key: row[key] for key in row.keys()}  # noqa: SIM118


class OpStore:
    """Almacén operativo de osap-api respaldado por SQLite."""

    def __init__(self, path: str = "osap_api.db") -> None:
        self._path = path
        parent = Path(path).parent
        if str(parent):
            parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_suggestions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    location TEXT NOT NULL,
                    mapping TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    admin_message TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    decided_by TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS providers (
                    provider_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'dynamic',
                    base_url TEXT,
                    wired INTEGER NOT NULL DEFAULT 0,
                    config TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    # --- sugerencias de fuentes ---------------------------------------------

    def list_suggestions(self) -> list[dict[str, object]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM source_suggestions ORDER BY created_at"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def add_suggestion(
        self,
        suggestion_id: str,
        name: str,
        source_type: str,
        location: str,
        mapping: dict[str, object],
        requested_by: str,
    ) -> dict[str, object]:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO source_suggestions (id, name, type, location, mapping, "
                "requested_by, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
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
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM source_suggestions WHERE id = ?", (suggestion_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def resolve_suggestion(
        self, suggestion_id: str, status: str, message: str, decided_by: str
    ) -> dict[str, object] | None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE source_suggestions SET status = ?, admin_message = ?, "
                "decided_at = ?, decided_by = ? WHERE id = ?",
                (status, message, _now(), decided_by, suggestion_id),
            )
        return self.get_suggestion(suggestion_id)

    def pending_suggestion_count(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM source_suggestions WHERE status = 'pending'"
            ).fetchone()
        return int(row["n"])

    # --- proveedores dinámicos ----------------------------------------------

    def list_providers(self) -> list[dict[str, object]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM providers ORDER BY name").fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_provider(self, provider_id: str) -> dict[str, object] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM providers WHERE provider_id = ?", (provider_id,)).fetchone()
        return _row_to_dict(row) if row else None

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
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO providers (provider_id, name, kind, base_url, wired, config, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(provider_id) DO UPDATE SET name = excluded.name, "
                "base_url = excluded.base_url, wired = excluded.wired, config = excluded.config",
                (provider_id, name, kind, base_url, int(wired), payload, _now()),
            )
        row = self.get_provider(provider_id)
        assert row is not None
        return row

    def set_provider_wired(self, provider_id: str, wired: bool) -> dict[str, object] | None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE providers SET wired = ? WHERE provider_id = ?", (int(wired), provider_id)
            )
        return self.get_provider(provider_id)

    # --- configuración operativa --------------------------------------------

    def get_config(self, key: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_config(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO app_config (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, _now()),
            )
