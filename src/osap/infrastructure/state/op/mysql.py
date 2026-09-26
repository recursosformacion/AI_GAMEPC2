"""Almacén operativo respaldado por MySQL (SQL + schema)."""

from __future__ import annotations

import json
import logging

import pymysql
from pymysql.cursors import DictCursor

from .memory import MemoryStore as _MemoryStore
from .memory import now as _now

_LOGGER = logging.getLogger("osap.state")


class _MysqlStore(_MemoryStore):
    """Almacén operativo respaldado por MySQL."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        super().__init__()
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
            ssl_disabled=str(self._params["host"]) in ("127.0.0.1", "localhost"),
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

    def _ensure_voicing_term_width(self) -> None:
        """Amplía `index_work_voicings.term` a 64: hay términos CPDL normalizados >32."""
        rows = self._run(
            "SELECT CHARACTER_MAXIMUM_LENGTH AS n FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'index_work_voicings' "
            "AND COLUMN_NAME = 'term'"
        )
        if rows and int(str(rows[0]["n"] or 0)) < 64:
            self._run("ALTER TABLE index_work_voicings MODIFY term VARCHAR(64) NOT NULL")

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
                person_id VARCHAR(36),
                catalogue VARCHAR(255),
                catalogue_key VARCHAR(128),
                year SMALLINT,
                instrumentation VARCHAR(255),
                genre_id INT UNSIGNED,
                source_count TINYINT NOT NULL DEFAULT 0,
                updated_at VARCHAR(64) NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uq_idx_title_composer (title_key(191), person_id),
                KEY idx_idx_composer (person_id),
                KEY idx_idx_composer_name (composer_name),
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
                -- Identidad de origen (dos niveles del modelo storage):
                --   source_rep_id = edición (p. ej. cpdlno) / '' en proveedores sin edición.
                --   resource_id   = `works_resources.id` / 0 en proveedores sin resource.
                -- Ambos con DEFAULT para que la clave única siga siendo idempotente en los
                -- proveedores legacy (OMR/IMSLP/MusicBrainz), donde no existen.
                source_rep_id VARCHAR(64) NOT NULL DEFAULT '',
                resource_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
                format VARCHAR(32) NOT NULL,
                download_url TEXT,
                title_provider VARCHAR(1024),
                available TINYINT NOT NULL DEFAULT 0,
                quality TINYINT NOT NULL DEFAULT 0,
                content_hash CHAR(64) NULL,
                xml_title VARCHAR(512) NULL,
                xml_composer VARCHAR(255) NULL,
                PRIMARY KEY (id),
                KEY idx_idxrep_work (work_id),
                KEY idx_rep_content_hash (content_hash),
                -- Identidad de recurso (CPDL) + el discriminante legacy `title_provider`:
                -- en proveedores sin identidad (`''`/0) la clave equivale a la antigua
                -- (work_id, provider, format, title_provider) y NO colapsa filas válidas.
                UNIQUE KEY uq_idxrep
                    (work_id, provider, source_rep_id, resource_id, format, title_provider(255))
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS index_work_voicings (
                work_id BIGINT UNSIGNED NOT NULL,
                kind VARCHAR(16) NOT NULL DEFAULT 'cpdl',
                term VARCHAR(64) NOT NULL,
                PRIMARY KEY (work_id, kind, term),
                KEY idx_work_voicing_term (term, kind)
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
        self._run(
            """
            CREATE TABLE IF NOT EXISTS correction_requests (
                id VARCHAR(64) PRIMARY KEY,
                kind VARCHAR(32) NOT NULL,
                entity_id VARCHAR(255),
                entity_provider VARCHAR(128),
                `field` VARCHAR(128),
                current_value VARCHAR(1024),
                proposed_value VARCHAR(1024),
                message TEXT NOT NULL,
                contact_email VARCHAR(255),
                requested_by VARCHAR(255),
                requested_by_name VARCHAR(255),
                requested_by_email VARCHAR(255),
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                admin_message TEXT,
                created_at VARCHAR(64) NOT NULL,
                decided_at VARCHAR(64),
                decided_by VARCHAR(255)
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS work_selections (
                work_id VARCHAR(128) PRIMARY KEY,
                selection_json TEXT NOT NULL,
                updated_at VARCHAR(64) NOT NULL
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )

    def _migrate(self) -> None:
        """Migraciones idempotentes sobre tablas ya existentes.

        NO se ejecutan al arrancar: las lanza `script/migrate_index_schema.py` una vez por
        despliegue (evita DDL concurrente con varias réplicas). La creación de tablas
        (`CREATE TABLE IF NOT EXISTS`) sí ocurre en `_init`.
        """
        self._ensure_voicing_term_width()
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

        # Columnas de identidad del solicitante en correction_requests (tablas antiguas).
        corr_cols = self._run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'correction_requests'"
        )
        corr_existing = {str(r["column_name"]) for r in corr_cols} if corr_cols else set()
        for col, ddl in (
            (
                "requested_by_name",
                "ALTER TABLE correction_requests ADD COLUMN requested_by_name VARCHAR(255)",
            ),
            (
                "requested_by_email",
                "ALTER TABLE correction_requests ADD COLUMN requested_by_email VARCHAR(255)",
            ),
        ):
            if col not in corr_existing:
                self._run(ddl)

        # SHA-256 del contenido de la representación (dedupe por fichero idéntico; lo rellena
        # script/hash_index_representations.py). Mismo esquema en local y producción.
        rep_cols = self._run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'index_representations'"
        )
        rep_existing = {str(r["column_name"]) for r in rep_cols} if rep_cols else set()
        if "content_hash" not in rep_existing:
            self._run("ALTER TABLE index_representations ADD COLUMN content_hash CHAR(64) NULL")
        # Metadatos internos del MusicXML (auditoría de títulos/compositor OMR; los rellena
        # script/audit_omr_titles.py al abrir cada fichero).
        if "xml_title" not in rep_existing:
            self._run("ALTER TABLE index_representations ADD COLUMN xml_title VARCHAR(512) NULL")
        if "xml_composer" not in rep_existing:
            self._run("ALTER TABLE index_representations ADD COLUMN xml_composer VARCHAR(255) NULL")
        # Identidad de origen CPDL (edición + resource). Legacy se rellena con '' / 0 para
        # no romper la unicidad de los proveedores sin identidad.
        if "source_rep_id" not in rep_existing:
            self._run(
                "ALTER TABLE index_representations "
                "ADD COLUMN source_rep_id VARCHAR(64) NOT NULL DEFAULT ''"
            )
        if "resource_id" not in rep_existing:
            self._run(
                "ALTER TABLE index_representations "
                "ADD COLUMN resource_id BIGINT UNSIGNED NOT NULL DEFAULT 0"
            )
        # La única antigua (work_id, provider, format, title_provider(255)) impedía tener
        # varias ediciones CPDL del mismo formato. Se añade la identidad de recurso
        # (`source_rep_id`, `resource_id`) MANTENIENDO `title_provider` como discriminante
        # legacy: así los proveedores sin identidad no pierden filas.
        _uq_wanted = [
            "work_id", "provider", "source_rep_id", "resource_id", "format", "title_provider",
        ]
        uq_rows = self._run(
            "SELECT column_name FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'index_representations' "
            "AND index_name = 'uq_idxrep' ORDER BY seq_in_index"
        )
        uq_existing = [str(r["column_name"]) for r in uq_rows] if uq_rows else []
        if uq_existing != _uq_wanted:
            if uq_existing:
                self._run("ALTER TABLE index_representations DROP INDEX uq_idxrep")
                # Solo colisionarían filas idénticas en TODOS los campos de la clave; con el
                # discriminante legacy incluido, esto no debería borrar nada.
                self._run(
                    "DELETE r1 FROM index_representations r1 JOIN index_representations r2 "
                    "ON r1.work_id = r2.work_id AND r1.provider = r2.provider "
                    "AND r1.source_rep_id = r2.source_rep_id AND r1.resource_id = r2.resource_id "
                    "AND r1.format = r2.format AND r1.title_provider <=> r2.title_provider "
                    "AND r1.id > r2.id"
                )
            self._run(
                "ALTER TABLE index_representations ADD UNIQUE KEY uq_idxrep "
                "(work_id, provider, source_rep_id, resource_id, format, title_provider(255))"
            )

        # El índice referencia a la persona (`persons`) como `person_id`; antes se llamó
        # `composer_id` (rol). Se mantiene `person_id` como nombre único de la clave.
        work_cols = self._run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'index_works'"
        )
        work_existing = {str(r["column_name"]) for r in work_cols} if work_cols else set()
        if "composer_id" in work_existing and "person_id" not in work_existing:
            self._run("ALTER TABLE index_works CHANGE composer_id person_id VARCHAR(36) NULL")
        elif "person_id" not in work_existing:
            self._run("ALTER TABLE index_works ADD COLUMN person_id VARCHAR(36) NULL")
        # El anclaje por título busca por `composer_name` (LIMIT 500): sin índice era un full
        # scan de index_works por compositor (el rebuild pasaba de minutos a horas).
        composer_name_index = self._run(
            "SELECT index_name FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'index_works' "
            "AND index_name = 'idx_idx_composer_name'"
        )
        if not composer_name_index:
            self._run("CREATE INDEX idx_idx_composer_name ON index_works (composer_name)")

        # Colaciones: unificar la BD a `utf8mb4_unicode_ci`. Con `utf8mb4_general_ci` en una
        # tabla, cualquier JOIN/compare con otra tabla de colación distinta falla (error 1267);
        # era el caso de `works ⨝ persons` en osap-storage.
        mixed = self._run(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_collation = 'utf8mb4_general_ci'"
        )
        for row in mixed or []:
            table = str(row["table_name"])
            self._run(
                f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        rep_index = self._run(
            "SELECT index_name FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'index_representations' "
            "AND index_name = 'idx_rep_content_hash'"
        )
        if not rep_index:
            self._run("CREATE INDEX idx_rep_content_hash ON index_representations (content_hash)")

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

    def list_corrections(self) -> list[dict[str, object]]:
        return self._run("SELECT * FROM correction_requests ORDER BY created_at DESC")

    def add_correction(
        self,
        correction_id: str,
        kind: str,
        entity_id: str | None,
        entity_provider: str | None,
        field: str | None,
        current_value: str | None,
        proposed_value: str | None,
        message: str,
        contact_email: str | None,
        requested_by: str | None,
        requested_by_name: str | None = None,
        requested_by_email: str | None = None,
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO correction_requests (id, kind, entity_id, entity_provider, `field`, "
            "current_value, proposed_value, message, contact_email, requested_by, "
            "requested_by_name, requested_by_email, status, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s)",
            (
                correction_id,
                kind,
                entity_id,
                entity_provider,
                field,
                current_value,
                proposed_value,
                message,
                contact_email,
                requested_by,
                requested_by_name,
                requested_by_email,
                _now(),
            ),
        )
        row = self.get_correction(correction_id)
        assert row is not None
        return row

    def get_correction(self, correction_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM correction_requests WHERE id = %s", (correction_id,))
        return rows[0] if rows else None

    def resolve_correction(
        self, correction_id: str, status: str, message: str, decided_by: str
    ) -> dict[str, object] | None:
        self._run(
            "UPDATE correction_requests SET status = %s, admin_message = %s, "
            "decided_at = %s, decided_by = %s WHERE id = %s",
            (status, message, _now(), decided_by, correction_id),
        )
        return self.get_correction(correction_id)

    def pending_correction_count(self) -> int:
        rows = self._run("SELECT COUNT(*) AS n FROM correction_requests WHERE status = 'pending'")
        return int(str(rows[0]["n"])) if rows else 0

    def get_work_selection(self, work_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM work_selections WHERE work_id = %s", (work_id,))
        return rows[0] if rows else None

    def set_work_selection(self, work_id: str, selection_json: str) -> dict[str, object]:
        self._run(
            "INSERT INTO work_selections (work_id, selection_json, updated_at) "
            "VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE selection_json = VALUES(selection_json), "
            "updated_at = VALUES(updated_at)",
            (work_id, selection_json, _now()),
        )
        row = self.get_work_selection(work_id)
        assert row is not None
        return row

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


