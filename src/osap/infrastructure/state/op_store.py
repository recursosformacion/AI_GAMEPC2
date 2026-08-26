"""Base de datos operativa de osap-api (MySQL).

Aloja SOLO estado operativo del propio osap-api, nunca una copia del catálogo de
osap-storage. Contiene: sugerencias de fuentes/proveedores y su auditoría, proveedores
dinámicos + configuración de conectores, y configuración operativa persistente.

`OpStore` es una factoría: intenta usar MySQL y, si no está disponible (usuario/BD sin
crear en el entorno), degrada a un almacén en memoria para no tumbar el servicio.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pymysql
from pymysql.cursors import DictCursor

_LOGGER = logging.getLogger("osap.state")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class _MemoryStore:
    """Almacén en memoria con la misma interfaz (fallback cuando MySQL no está)."""

    def __init__(self) -> None:
        self._suggestions: list[dict[str, object]] = []
        self._providers: list[dict[str, object]] = []
        self._config: dict[str, str] = {}

    def list_suggestions(self) -> list[dict[str, object]]:
        return list(self._suggestions)

    def add_suggestion(
        self,
        suggestion_id: str,
        name: str,
        source_type: str,
        location: str,
        mapping: dict[str, object],
        requested_by: str,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "id": suggestion_id,
            "name": name,
            "type": source_type,
            "location": location,
            "mapping": json.dumps(mapping, ensure_ascii=False),
            "requested_by": requested_by,
            "status": "pending",
            "admin_message": None,
            "created_at": _now(),
            "decided_at": None,
            "decided_by": None,
        }
        self._suggestions.append(row)
        return row

    def get_suggestion(self, suggestion_id: str) -> dict[str, object] | None:
        for row in self._suggestions:
            if row["id"] == suggestion_id:
                return row
        return None

    def resolve_suggestion(
        self, suggestion_id: str, status: str, message: str, decided_by: str
    ) -> dict[str, object] | None:
        for row in self._suggestions:
            if row["id"] == suggestion_id:
                row["status"] = status
                row["admin_message"] = message
                row["decided_at"] = _now()
                row["decided_by"] = decided_by
                return row
        return None

    def pending_suggestion_count(self) -> int:
        return sum(1 for r in self._suggestions if r["status"] == "pending")

    def suggestion_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {"pending": 0, "approved": 0, "cancelled": 0, "total": 0}
        for r in self._suggestions:
            status = str(r.get("status") or "pending")
            counts[status] = counts.get(status, 0) + 1
            counts["total"] += 1
        return counts

    def list_providers(self) -> list[dict[str, object]]:
        return list(self._providers)

    def get_provider(self, provider_id: str) -> dict[str, object] | None:
        for row in self._providers:
            if row["provider_id"] == provider_id:
                return row
        return None

    def upsert_provider(
        self,
        provider_id: str,
        name: str,
        base_url: str | None = None,
        wired: bool = False,
        kind: str = "dynamic",
        config: dict[str, object] | None = None,
        description: dict[str, str] | str | None = None,
        endpoints: dict[str, object] | None = None,
        mapping: dict[str, object] | None = None,
        resources: dict[str, object] | None = None,
        transforms: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = json.dumps(config or {}, ensure_ascii=False)
        for existing in self._providers:
            if existing["provider_id"] == provider_id:
                existing.update({
                    "name": name, "base_url": base_url, "wired": int(wired),
                    "config": payload, "description": description,
                    "endpoints": endpoints, "mapping": mapping,
                    "resources": resources, "transforms": transforms,
                })
                return existing
        row: dict[str, object] = {
            "provider_id": provider_id,
            "name": name,
            "kind": kind,
            "base_url": base_url,
            "wired": int(wired),
            "config": payload,
            "description": description,
            "endpoints": endpoints,
            "mapping": mapping,
            "resources": resources,
            "transforms": transforms,
            "created_at": _now(),
        }
        self._providers.append(row)
        return row

    def delete_provider(self, provider_id: str) -> bool:
        before = len(self._providers)
        self._providers = [r for r in self._providers if r["provider_id"] != provider_id]
        return len(self._providers) < before

    def set_provider_wired(self, provider_id: str, wired: bool) -> dict[str, object] | None:
        for row in self._providers:
            if row["provider_id"] == provider_id:
                row["wired"] = int(wired)
                return row
        return None

    def get_config(self, key: str) -> str | None:
        return self._config.get(key)

    def set_config(self, key: str, value: str) -> None:
        self._config[key] = value


class _MysqlStore(_MemoryStore):
    """Almacén operativo respaldado por MySQL."""

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
                description TEXT,
                wired TINYINT NOT NULL DEFAULT 0,
                config TEXT NOT NULL,
                endpoints TEXT,
                mapping TEXT,
                resources TEXT,
                transforms TEXT,
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
        self._run(
            """
            CREATE TABLE IF NOT EXISTS index_works (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                title VARCHAR(1024) NOT NULL,
                title_key VARCHAR(255) NOT NULL,
                composer_name VARCHAR(255),
                composer_id VARCHAR(36),
                catalogue VARCHAR(255),
                catalogue_key VARCHAR(128),
                year SMALLINT,
                instrumentation VARCHAR(255),
                source_count TINYINT NOT NULL DEFAULT 0,
                updated_at VARCHAR(64) NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uq_idx_title_composer (title_key(191), composer_id),
                KEY idx_idx_composer (composer_id),
                KEY idx_idx_catalogue (catalogue_key),
                KEY idx_idx_title (title_key)
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS index_representations (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                work_id BIGINT UNSIGNED NOT NULL,
                provider VARCHAR(64) NOT NULL,
                format VARCHAR(32) NOT NULL,
                download_url TEXT,
                title_provider VARCHAR(1024),
                available TINYINT NOT NULL DEFAULT 0,
                quality TINYINT NOT NULL DEFAULT 0,
                PRIMARY KEY (id),
                KEY idx_idxrep_work (work_id),
                UNIQUE KEY uq_idxrep (work_id, provider, format, title_provider(255))
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                `key` VARCHAR(64) PRIMARY KEY,
                value VARCHAR(255) NOT NULL,
                updated_at VARCHAR(64) NOT NULL
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._migrate()

    def _migrate(self) -> None:
        """Migraciones idempotentes sobre tablas ya existentes."""
        columns = self._run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'providers'"
        )
        existing = {str(r["column_name"]) for r in columns} if columns else set()
        for col, ddl in (
            ("description", "ALTER TABLE providers ADD COLUMN description TEXT"),
            ("endpoints", "ALTER TABLE providers ADD COLUMN endpoints TEXT"),
            ("mapping", "ALTER TABLE providers ADD COLUMN mapping TEXT"),
            ("resources", "ALTER TABLE providers ADD COLUMN resources TEXT"),
            ("transforms", "ALTER TABLE providers ADD COLUMN transforms TEXT"),
        ):
            if col not in existing:
                self._run(ddl)

        # Índice FULLTEXT para la búsqueda de texto libre del índice de obras.
        # `LIKE '%término%'` hace full scan de index_works (355k filas); MATCH usa este
        # índice y mantiene el esquema idéntico en local y producción por construcción.
        ft = self._run(
            "SELECT index_name FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'index_works' "
            "AND index_name = 'ft_idx_title_composer'"
        )
        if not ft:
            try:
                self._run(
                    "ALTER TABLE index_works ADD FULLTEXT INDEX ft_idx_title_composer (title, composer_name)"
                )
            except pymysql.err.OperationalError:
                # Innodb o versión sin FULLTEXT: se deja el LIKE (funciona, más lento).
                _LOGGER.warning("FULLTEXT no disponible en index_works; se usa LIKE")
            except pymysql.err.InternalError:
                _LOGGER.warning("FULLTEXT no disponible en index_works; se usa LIKE")

    def get_sync_state(self, key: str) -> str | None:
        rows = self._run("SELECT value FROM sync_state WHERE `key` = %s", (key,))
        return str(rows[0]["value"]) if rows else None

    def set_sync_state(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO sync_state (`key`, value, updated_at) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)",
            (key, value, _now()),
        )

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

    def suggestion_counts(self) -> dict[str, int]:
        rows = self._run("SELECT status, COUNT(*) AS n FROM source_suggestions GROUP BY status")
        counts: dict[str, int] = {"pending": 0, "approved": 0, "cancelled": 0, "total": 0}
        for r in rows:
            status = str(r.get("status") or "pending")
            count = int(str(r.get("n") or 0))
            counts[status] = counts.get(status, 0) + count
            counts["total"] += count
        return counts

    def list_providers(self) -> list[dict[str, object]]:
        rows = self._run("SELECT * FROM providers ORDER BY name")
        return [_decode_provider_row(r) for r in rows]

    def get_provider(self, provider_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM providers WHERE provider_id = %s", (provider_id,))
        return _decode_provider_row(rows[0]) if rows else None

    def upsert_provider(
        self,
        provider_id: str,
        name: str,
        base_url: str | None = None,
        wired: bool = False,
        kind: str = "dynamic",
        config: dict[str, object] | None = None,
        description: dict[str, str] | str | None = None,
        endpoints: dict[str, object] | None = None,
        mapping: dict[str, object] | None = None,
        resources: dict[str, object] | None = None,
        transforms: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = json.dumps(config or {}, ensure_ascii=False)
        description_json = _encode_description(description)
        endpoints_json = json.dumps(endpoints, ensure_ascii=False) if endpoints is not None else None
        mapping_json = json.dumps(mapping, ensure_ascii=False) if mapping is not None else None
        resources_json = json.dumps(resources, ensure_ascii=False) if resources is not None else None
        transforms_json = json.dumps(transforms, ensure_ascii=False) if transforms is not None else None
        self._run(
            "INSERT INTO providers (provider_id, name, kind, base_url, description, wired, "
            "config, endpoints, mapping, resources, transforms, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE name = VALUES(name), base_url = VALUES(base_url), "
            "description = VALUES(description), wired = VALUES(wired), config = VALUES(config), "
            "endpoints = COALESCE(VALUES(endpoints), endpoints), "
            "mapping = COALESCE(VALUES(mapping), mapping), "
            "resources = COALESCE(VALUES(resources), resources), "
            "transforms = COALESCE(VALUES(transforms), transforms)",
            (provider_id, name, kind, base_url, description_json, int(wired), payload,
             endpoints_json, mapping_json, resources_json, transforms_json, _now()),
        )
        row = self.get_provider(provider_id)
        assert row is not None
        return row

    def delete_provider(self, provider_id: str) -> bool:
        existed = bool(self.get_provider(provider_id))
        self._run("DELETE FROM providers WHERE provider_id = %s", (provider_id,))
        return existed

    def set_provider_wired(self, provider_id: str, wired: bool) -> dict[str, object] | None:
        self._run("UPDATE providers SET wired = %s WHERE provider_id = %s", (int(wired), provider_id))
        return self.get_provider(provider_id)

    def get_config(self, key: str) -> str | None:
        rows = self._run("SELECT value FROM app_config WHERE `key` = %s", (key,))
        return str(rows[0]["value"]) if rows else None

    def set_config(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO app_config (`key`, value, updated_at) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)",
            (key, value, _now()),
        )


def _decode_provider_row(row: dict[str, object]) -> dict[str, object]:
    """Parsea las columnas JSON de `providers` para el API/admin."""
    out = dict(row)
    description_raw = row.get("description")
    if description_raw:
        try:
            parsed = json.loads(str(description_raw))
            out["description"] = parsed if isinstance(parsed, dict) else {"en": str(parsed)}
        except (TypeError, ValueError):
            out["description"] = {"en": str(description_raw)}
    else:
        out["description"] = {}
    for col in ("config", "endpoints", "mapping", "resources", "transforms"):
        raw = row.get(col)
        if raw:
            try:
                out[col] = json.loads(str(raw))
            except (TypeError, ValueError):
                out[col] = raw
        else:
            out[col] = {}
    return out


def _encode_description(description: dict[str, str] | str | None) -> str | None:
    """Codifica la descripción multi-idioma a JSON para la columna `description`."""
    if not description:
        return None
    if isinstance(description, str):
        return json.dumps({"en": description}, ensure_ascii=False)
    return json.dumps(description, ensure_ascii=False)


def build_op_store(
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
        store._migrate()
        return store
    except pymysql.err.OperationalError as exc:
        _LOGGER.warning("MySQL operativo no disponible (%s); usando almacén en memoria", exc)
        return _MemoryStore()
