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

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str,
        port: int = 3306,
        read_only: bool = False,
    ) -> None:
        super().__init__()
        self._port = port
        self._params = {
            "host": host,
            "user": user,
            "password": password,
            "database": database,
        }
        # En modo solo lectura (osap_ro por túnel) el usuario no tiene DDL: crear tablas
        # lanzaría 1142 y la factoría degradaría a memoria perdiendo la config real.
        if not read_only:
            self._init()

    def _conn(self) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=self._params["host"],
            user=self._params["user"],
            password=self._params["password"],
            database=self._params["database"],
            port=self._port,
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
            CREATE TABLE IF NOT EXISTS notifications (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                user_id CHAR(36) NULL,
                kind VARCHAR(32) NOT NULL,
                title VARCHAR(200) NOT NULL,
                body TEXT NOT NULL,
                link VARCHAR(500) NULL,
                created_at VARCHAR(64) NOT NULL,
                read_at VARCHAR(64) NULL,
                INDEX idx_notifications_user (user_id, read_at)
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
                KEY idx_idx_title (title_key),
                KEY idx_idx_updated_at (updated_at, id)
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
        self._init_amigos()

    def _init_amigos(self) -> None:
        """Tablas de «Los amigos» (grupos, membresias, articulos, recursos, auditoria).

        `CREATE TABLE IF NOT EXISTS` (idempotente, aditivo). La migracion dedicada
        `script/migrate_amigos_schema.py` permite dry-run y verificacion previa.
        """
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_groups (
                id CHAR(32) PRIMARY KEY,
                slug VARCHAR(96) NOT NULL,
                name VARCHAR(255) NOT NULL,
                kind VARCHAR(32) NOT NULL DEFAULT 'coral',
                description TEXT,
                image_url VARCHAR(1024),
                website VARCHAR(1024),
                email VARCHAR(254),
                logo_url VARCHAR(1024),
                status VARCHAR(16) NOT NULL DEFAULT 'active',
                editorial_mode VARCHAR(16) NOT NULL DEFAULT 'moderated',
                created_by CHAR(36),
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                    ON UPDATE CURRENT_TIMESTAMP(6),
                UNIQUE KEY uq_amigos_group_slug (slug)
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_members (
                group_id CHAR(32) NOT NULL,
                user_id CHAR(36) NOT NULL,
                role VARCHAR(16) NOT NULL DEFAULT 'collaborator',
                status VARCHAR(16) NOT NULL DEFAULT 'active',
                granted_by CHAR(36),
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                    ON UPDATE CURRENT_TIMESTAMP(6),
                PRIMARY KEY (group_id, user_id),
                KEY idx_amigos_member_user (user_id),
                CONSTRAINT fk_amigos_member_group FOREIGN KEY (group_id)
                    REFERENCES amigos_groups (id) ON DELETE RESTRICT
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_articles (
                id CHAR(32) PRIMARY KEY,
                group_id CHAR(32),
                scope VARCHAR(16) NOT NULL DEFAULT 'group',
                title VARCHAR(512) NOT NULL,
                slug VARCHAR(200) NOT NULL,
                event_date DATE NOT NULL,
                summary TEXT,
                body LONGTEXT,
                cover_url VARCHAR(1024),
                author_user_id CHAR(36) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'draft',
                published_at DATETIME(6),
                reviewed_by CHAR(36),
                reviewed_at DATETIME(6),
                review_note VARCHAR(512),
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                    ON UPDATE CURRENT_TIMESTAMP(6),
                UNIQUE KEY uq_amigos_article_slug (group_id, slug),
                KEY idx_amigos_article_status (status),
                KEY idx_amigos_article_author (author_user_id),
                KEY idx_amigos_article_event (group_id, event_date),
                CONSTRAINT fk_amigos_article_group FOREIGN KEY (group_id)
                    REFERENCES amigos_groups (id) ON DELETE RESTRICT
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_media (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                article_id CHAR(32) NOT NULL,
                kind VARCHAR(16) NOT NULL,
                url VARCHAR(1024) NOT NULL,
                provider VARCHAR(32),
                video_id VARCHAR(64),
                caption VARCHAR(512),
                credit VARCHAR(512),
                position INT NOT NULL DEFAULT 0,
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                PRIMARY KEY (id),
                KEY idx_amigos_media_article (article_id, position),
                CONSTRAINT fk_amigos_media_article FOREIGN KEY (article_id)
                    REFERENCES amigos_articles (id) ON DELETE CASCADE
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_events (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                group_id CHAR(32),
                article_id CHAR(32),
                event_type VARCHAR(48) NOT NULL,
                actor CHAR(36),
                from_status VARCHAR(16),
                to_status VARCHAR(16),
                detail_json LONGTEXT,
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                PRIMARY KEY (id),
                KEY idx_amigos_event_group (group_id, created_at),
                KEY idx_amigos_event_article (article_id, created_at)
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        # Especialización por tipo de grupo: ficha de coral (1:1) + facetas multivalor.
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_coral_details (
                group_id CHAR(32) NOT NULL,
                foundation_date DATE,
                dissolution_date DATE,
                locality VARCHAR(160),
                region VARCHAR(160),
                country_code CHAR(2),
                venue VARCHAR(255),
                formation_type VARCHAR(48),
                member_count INT,
                website VARCHAR(1024),
                public_email VARCHAR(254),
                director_person_id VARCHAR(64),
                director_label VARCHAR(255),
                linked_entity VARCHAR(255),
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                    ON UPDATE CURRENT_TIMESTAMP(6),
                PRIMARY KEY (group_id),
                CONSTRAINT fk_amigos_coral_group FOREIGN KEY (group_id)
                    REFERENCES amigos_groups (id) ON DELETE CASCADE
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_coral_attributes (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                group_id CHAR(32) NOT NULL,
                facet VARCHAR(32) NOT NULL COMMENT 'repertoire|language',
                value VARCHAR(120) NOT NULL,
                position INT NOT NULL DEFAULT 0,
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                PRIMARY KEY (id),
                UNIQUE KEY uq_amigos_coral_attr (group_id, facet, value),
                KEY idx_amigos_coral_attr (group_id, facet, position),
                CONSTRAINT fk_amigos_coral_attr_group FOREIGN KEY (group_id)
                    REFERENCES amigos_coral_details (group_id) ON DELETE CASCADE
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        # Enlaces comunes del grupo (web/social): relación normalizada por tipo.
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_group_links (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                group_id CHAR(32) NOT NULL,
                kind VARCHAR(32) NOT NULL COMMENT 'facebook|instagram|other',
                label VARCHAR(64),
                url VARCHAR(1024) NOT NULL,
                position INT NOT NULL DEFAULT 0,
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                PRIMARY KEY (id),
                KEY idx_amigos_group_link (group_id, position),
                CONSTRAINT fk_amigos_group_link_group FOREIGN KEY (group_id)
                    REFERENCES amigos_groups (id) ON DELETE CASCADE
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        # Imágenes subidas (ficheros en osap-storage): registro para servirlos de forma segura.
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_uploads (
                file_id BIGINT UNSIGNED NOT NULL,
                group_id CHAR(32) NOT NULL,
                mime_type VARCHAR(64),
                size_bytes BIGINT UNSIGNED,
                created_by CHAR(36),
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                PRIMARY KEY (file_id),
                KEY idx_amigos_upload_group (group_id)
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        # Agenda: actuaciones/eventos (nombre distinto de amigos_events, que es auditoría).
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_actuaciones (
                id CHAR(32) PRIMARY KEY,
                slug VARCHAR(200) NOT NULL,
                title VARCHAR(512) NOT NULL,
                summary TEXT,
                description LONGTEXT,
                image_url VARCHAR(1024),
                kind VARCHAR(32) NOT NULL DEFAULT 'concert',
                modality VARCHAR(16) NOT NULL DEFAULT 'onsite',
                event_status VARCHAR(16) NOT NULL DEFAULT 'scheduled',
                editorial_status VARCHAR(16) NOT NULL DEFAULT 'draft',
                starts_on DATE NOT NULL,
                starts_at TIME,
                ends_on DATE,
                ends_at TIME,
                timezone VARCHAR(64),
                registration_deadline DATE,
                venue_name VARCHAR(255),
                venue_address VARCHAR(512),
                locality VARCHAR(160),
                region VARCHAR(160),
                country_code CHAR(2),
                latitude DECIMAL(9,6),
                longitude DECIMAL(9,6),
                map_url VARCHAR(1024),
                organizer_name VARCHAR(255),
                organizer_website VARCHAR(1024),
                event_url VARCHAR(1024),
                tickets_url VARCHAR(1024),
                price VARCHAR(120),
                access_info TEXT,
                public_contact VARCHAR(254),
                organizer_group_id CHAR(32),
                author_user_id CHAR(36) NOT NULL,
                last_verified_on DATE,
                internal_notes TEXT,
                weight TINYINT NOT NULL DEFAULT 5 COMMENT '1..9; primer criterio de orden (desc)',
                views INT UNSIGNED NOT NULL DEFAULT 0,
                expands INT UNSIGNED NOT NULL DEFAULT 0,
                buys INT UNSIGNED NOT NULL DEFAULT 0,
                source_email VARCHAR(254) COMMENT 'email de quien registra el anuncio',
                source_note VARCHAR(255) COMMENT 'texto libre cuando lo registra un admin global',
                published_at DATETIME(6),
                reviewed_by CHAR(36),
                reviewed_at DATETIME(6),
                review_note VARCHAR(512),
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                    ON UPDATE CURRENT_TIMESTAMP(6),
                UNIQUE KEY uq_amigos_actuacion_slug (slug),
                KEY idx_amigos_actuacion_date (starts_on),
                KEY idx_amigos_actuacion_status (editorial_status),
                KEY idx_amigos_actuacion_weight (weight),
                CONSTRAINT fk_amigos_actuacion_org FOREIGN KEY (organizer_group_id)
                    REFERENCES amigos_groups (id) ON DELETE SET NULL
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_actuacion_groups (
                actuacion_id CHAR(32) NOT NULL,
                group_id CHAR(32) NOT NULL,
                role VARCHAR(16) NOT NULL DEFAULT 'participant',
                PRIMARY KEY (actuacion_id, group_id),
                KEY idx_amigos_ag_group (group_id),
                CONSTRAINT fk_amigos_ag_actuacion FOREIGN KEY (actuacion_id)
                    REFERENCES amigos_actuaciones (id) ON DELETE CASCADE,
                CONSTRAINT fk_amigos_ag_group FOREIGN KEY (group_id)
                    REFERENCES amigos_groups (id) ON DELETE RESTRICT
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        # Columnas de la agenda añadidas a tablas ya existentes (idempotente/tolerante).
        for _col, _ddl in (
            ("weight", "TINYINT NOT NULL DEFAULT 5"),
            ("views", "INT UNSIGNED NOT NULL DEFAULT 0"),
            ("expands", "INT UNSIGNED NOT NULL DEFAULT 0"),
            ("buys", "INT UNSIGNED NOT NULL DEFAULT 0"),
            ("source_email", "VARCHAR(254) NULL"),
            ("source_note", "VARCHAR(255) NULL"),
        ):
            self._ensure_column("amigos_actuaciones", _col, _ddl)
        # Blog general + autorizaciones editoriales (blog/agenda).
        self._ensure_column("amigos_articles", "scope", "VARCHAR(16) NOT NULL DEFAULT 'group'")
        self._ensure_column_nullable("amigos_articles", "group_id", "CHAR(32) NULL")
        self._run(
            """
            CREATE TABLE IF NOT EXISTS amigos_authorizations (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                user_id CHAR(36) NOT NULL,
                scope VARCHAR(32) NOT NULL,
                direct_publish TINYINT(1) NOT NULL DEFAULT 0,
                granted_by CHAR(36),
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                    ON UPDATE CURRENT_TIMESTAMP(6),
                PRIMARY KEY (id),
                UNIQUE KEY uq_amigos_auth (scope, user_id)
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
            """
        )
        # Columnas comunes añadidas a grupos ya existentes (idempotente).
        self._ensure_column("amigos_groups", "website", "VARCHAR(1024) NULL")
        self._ensure_column("amigos_groups", "email", "VARCHAR(254) NULL")
        self._ensure_column("amigos_groups", "logo_url", "VARCHAR(1024) NULL")

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        # Nunca debe abortar el arranque del store: el usuario de la app puede no tener
        # privilegio ALTER (se registra y se continúa; la columna se añade vía migración DBA).
        try:
            rows = self._run(
                "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                (table, column),
            )
            if rows and int(str(rows[0]["n"])) == 0:
                self._run(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("no se pudo asegurar la columna %s.%s: %s", table, column, exc)

    def _ensure_column_nullable(self, table: str, column: str, ddl: str) -> None:
        try:
            self._run(f"ALTER TABLE {table} MODIFY {column} {ddl}")
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("no se pudo modificar %s.%s: %s", table, column, exc)

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

        # La portada lista las novedades por `updated_at` DESC: sin índice MySQL ordena toda
        # la tabla (filesort de ~350k filas) en cada carga. Índice compuesto (updated_at, id)
        # que sirve tanto el ORDER BY como el desempate.
        recent_index = self._run(
            "SELECT index_name FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'index_works' "
            "AND index_name = 'idx_idx_updated_at'"
        )
        if not recent_index:
            self._run("CREATE INDEX idx_idx_updated_at ON index_works (updated_at, id)")

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

    # --- contributions (aportaciones) -----------------------------------------
    # Tablas creadas por la migración preparada (script/migrate_contributions_schema.py),
    # que NO se ejecuta desde aquí. Escrituras compuestas en una sola transacción.

    def add_contribution(
        self,
        *,
        actor_user_id: str,
        operation: str,
        target_kind: str,
        target_id: str | None,
        declared_source: str | None,
        payload_json: str | None = None,
        relations: list[dict[str, object]],
        actor: str | None,
    ) -> dict[str, object]:
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO contributions (actor_user_id, operation, target_kind, target_id, "
                    "declared_source, payload_json, status) VALUES (%s,%s,%s,%s,%s,%s,'draft')",
                    (actor_user_id, operation, target_kind, target_id, declared_source, payload_json),
                )
                cid = int(cur.lastrowid or 0)
                for rel in relations:
                    cur.execute(
                        "INSERT INTO contribution_relations (contribution_id, relation_kind, "
                        "relation_code, person_id, person_name, validation_status) "
                        "VALUES (%s,%s,%s,%s,%s,'pending')",
                        (
                            cid,
                            rel["relation_kind"],
                            rel["relation_code"],
                            rel.get("person_id"),
                            rel.get("person_name"),
                        ),
                    )
                cur.execute(
                    "INSERT INTO contribution_events (contribution_id, event_type, to_status, actor) "
                    "VALUES (%s,'created','draft',%s)",
                    (cid, actor),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        row = self.get_contribution(cid)
        assert row is not None
        return row

    def get_contribution(self, contribution_id: int) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM contributions WHERE id = %s", (contribution_id,))
        return rows[0] if rows else None

    def list_contributions_by_actor(
        self, actor_user_id: str, *, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        total_rows = self._run(
            "SELECT COUNT(*) AS n FROM contributions WHERE actor_user_id = %s", (actor_user_id,)
        )
        total = int(str(total_rows[0]["n"])) if total_rows else 0
        rows = self._run(
            "SELECT * FROM contributions WHERE actor_user_id = %s ORDER BY id DESC LIMIT %s OFFSET %s",
            (actor_user_id, limit, offset),
        )
        return rows, total

    def list_contributions_for_review(
        self, statuses: list[str], *, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        placeholders = ",".join(["%s"] * len(statuses))
        total_rows = self._run(
            f"SELECT COUNT(*) AS n FROM contributions WHERE status IN ({placeholders})",
            tuple(statuses),
        )
        total = int(str(total_rows[0]["n"])) if total_rows else 0
        rows = self._run(
            f"SELECT * FROM contributions WHERE status IN ({placeholders}) ORDER BY id ASC "
            "LIMIT %s OFFSET %s",
            (*statuses, limit, offset),
        )
        return rows, total

    def list_contribution_relations(self, contribution_id: int) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM contribution_relations WHERE contribution_id = %s ORDER BY id",
            (contribution_id,),
        )

    def list_contribution_artifacts(self, contribution_id: int) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM contribution_artifacts WHERE contribution_id = %s ORDER BY id",
            (contribution_id,),
        )

    def list_contribution_events(self, contribution_id: int) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM contribution_events WHERE contribution_id = %s ORDER BY id",
            (contribution_id,),
        )

    def add_contribution_event(
        self,
        *,
        contribution_id: int,
        event_type: str,
        from_status: str | None = None,
        to_status: str | None = None,
        relation_id: int | None = None,
        detail_json: str | None = None,
        actor: str | None = None,
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO contribution_events (contribution_id, event_type, from_status, to_status, "
            "relation_id, detail_json, actor) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (contribution_id, event_type, from_status, to_status, relation_id, detail_json, actor),
        )
        rows = self._run(
            "SELECT * FROM contribution_events WHERE contribution_id = %s ORDER BY id DESC LIMIT 1",
            (contribution_id,),
        )
        assert rows
        return rows[0]

    def contribution_artifact_exists(self, contribution_id: int, file_id: int) -> bool:
        rows = self._run(
            "SELECT id FROM contribution_artifacts WHERE contribution_id = %s AND file_id = %s LIMIT 1",
            (contribution_id, file_id),
        )
        return bool(rows)

    def add_contribution_artifact(
        self, *, contribution_id: int, file_id: int, kind: str | None, actor: str | None
    ) -> dict[str, object]:
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO contribution_artifacts (contribution_id, file_id, kind) "
                    "VALUES (%s,%s,%s)",
                    (contribution_id, file_id, kind),
                )
                aid = int(cur.lastrowid or 0)
                cur.execute(
                    "INSERT INTO contribution_events (contribution_id, event_type, actor, detail_json) "
                    "VALUES (%s,'artifact_added',%s,%s)",
                    (contribution_id, actor, json.dumps({"file_id": file_id})),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        rows = self._run("SELECT * FROM contribution_artifacts WHERE id = %s", (aid,))
        assert rows
        return rows[0]

    def set_contribution_status(
        self,
        *,
        contribution_id: int,
        status: str,
        reviewed_by: str | None,
        review_note: str | None,
        event_type: str,
        actor: str | None,
    ) -> dict[str, object] | None:
        existing = self.get_contribution(contribution_id)
        if existing is None:
            return None
        from_status = str(existing["status"])
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE contributions SET status=%s, "
                    "reviewed_by=COALESCE(%s, reviewed_by), review_note=COALESCE(%s, review_note), "
                    "reviewed_at=CASE WHEN %s IS NULL THEN reviewed_at ELSE NOW(6) END "
                    "WHERE id=%s",
                    (status, reviewed_by, review_note, reviewed_by, contribution_id),
                )
                cur.execute(
                    "INSERT INTO contribution_events "
                    "(contribution_id, event_type, from_status, to_status, actor) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (contribution_id, event_type, from_status, status, actor),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_contribution(contribution_id)

    def update_contribution_relation_validation(
        self,
        *,
        contribution_id: int,
        relation_id: int,
        validation_status: str,
        validated_by: str | None,
        actor: str | None,
        note: str | None,
    ) -> dict[str, object] | None:
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM contribution_relations WHERE id = %s AND contribution_id = %s",
                    (relation_id, contribution_id),
                )
                if cur.fetchone() is None:
                    conn.rollback()
                    return None
                cur.execute(
                    "UPDATE contribution_relations SET validation_status=%s, validated_by=%s, "
                    "validated_at=NOW(6) WHERE id=%s",
                    (validation_status, validated_by, relation_id),
                )
                cur.execute(
                    "INSERT INTO contribution_events "
                    "(contribution_id, event_type, relation_id, detail_json, actor) "
                    "VALUES (%s,'relation_validated',%s,%s,%s)",
                    (
                        contribution_id,
                        relation_id,
                        json.dumps({"validation_status": validation_status, "note": note}),
                        actor,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        rows = self._run("SELECT * FROM contribution_relations WHERE id = %s", (relation_id,))
        return rows[0] if rows else None

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

    # --- Notificaciones (campana de la app) ----------------------------------

    def add_notification(
        self, *, user_id: str | None, kind: str, title: str, body: str, link: str | None = None
    ) -> dict[str, object]:
        now = _now()
        self._run(
            "INSERT INTO notifications (user_id, kind, title, body, link, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, kind, title, body, link, now),
        )
        return {
            "user_id": user_id,
            "kind": kind,
            "title": title,
            "body": body,
            "link": link,
            "created_at": now,
            "read_at": None,
        }

    def list_notifications(
        self, *, user_id: str, include_global: bool, limit: int = 50
    ) -> list[dict[str, object]]:
        condition = "(user_id = %s OR user_id IS NULL)" if include_global else "user_id = %s"
        rows = self._run(
            "SELECT id, user_id, kind, title, body, link, created_at, read_at "
            f"FROM notifications WHERE {condition} ORDER BY created_at DESC, id DESC LIMIT %s",
            (user_id, limit),
        )
        return [dict(row) for row in rows]

    def count_unread_notifications(self, *, user_id: str, include_global: bool) -> int:
        condition = "(user_id = %s OR user_id IS NULL)" if include_global else "user_id = %s"
        rows = self._run(
            f"SELECT COUNT(*) AS c FROM notifications WHERE {condition} AND read_at IS NULL",
            (user_id,),
        )
        return int(str(rows[0]["c"])) if rows else 0

    def mark_notification_read(self, *, notification_id: int, user_id: str) -> bool:
        self._run(
            "UPDATE notifications SET read_at = %s "
            "WHERE id = %s AND read_at IS NULL AND (user_id = %s OR user_id IS NULL)",
            (_now(), notification_id, user_id),
        )
        return True

    def mark_all_notifications_read(self, *, user_id: str, include_global: bool) -> bool:
        condition = "(user_id = %s OR user_id IS NULL)" if include_global else "user_id = %s"
        self._run(
            f"UPDATE notifications SET read_at = %s WHERE {condition} AND read_at IS NULL",
            (_now(), user_id),
        )
        return True

    # --- «Los amigos»: grupos (MySQL) ----------------------------------------

    def add_amigos_group(
        self,
        *,
        group_id: str,
        slug: str,
        name: str,
        kind: str,
        description: str | None,
        image_url: str | None,
        editorial_mode: str,
        created_by: str | None,
        website: str | None = None,
        email: str | None = None,
        logo_url: str | None = None,
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO amigos_groups (id, slug, name, kind, description, image_url, "
            "website, email, logo_url, status, editorial_mode, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s,%s)",
            (group_id, slug, name, kind, description, image_url, website, email, logo_url,
             editorial_mode, created_by),
        )
        row = self.get_amigos_group(group_id)
        assert row is not None
        return row

    def get_amigos_group(self, group_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM amigos_groups WHERE id = %s", (group_id,))
        return rows[0] if rows else None

    def get_amigos_group_by_slug(self, slug: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM amigos_groups WHERE slug = %s", (slug,))
        return rows[0] if rows else None

    def list_amigos_groups(
        self, *, active_only: bool = True, kind: str | None = None
    ) -> list[dict[str, object]]:
        clauses: list[str] = []
        args: list[object] = []
        if active_only:
            clauses.append("status = 'active'")
        if kind is not None:
            clauses.append("kind = %s")
            args.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._run(f"SELECT * FROM amigos_groups {where} ORDER BY name", tuple(args))

    def update_amigos_group(self, group_id: str, **changes: object) -> dict[str, object] | None:
        allowed = {"name", "description", "image_url", "editorial_mode", "status",
                   "website", "email", "logo_url"}
        fields = [k for k in changes if k in allowed]
        if fields:
            assignments = ", ".join(f"{k} = %s" for k in fields)
            self._run(
                f"UPDATE amigos_groups SET {assignments} WHERE id = %s",
                (*[changes[k] for k in fields], group_id),
            )
        return self.get_amigos_group(group_id)

    # --- «Los amigos»: enlaces del grupo (MySQL) -----------------------------

    def replace_amigos_group_links(self, group_id: str, items: list[dict[str, object]]) -> None:
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM amigos_group_links WHERE group_id = %s", (group_id,))
                for item in items:
                    cur.execute(
                        "INSERT INTO amigos_group_links (group_id, kind, label, url, position) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (group_id, item.get("kind"), item.get("label"), item.get("url"),
                         int(str(item.get("position") or 0))),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_amigos_group_links(self, group_id: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM amigos_group_links WHERE group_id = %s ORDER BY position, id",
            (group_id,),
        )

    # --- «Los amigos»: imágenes subidas (MySQL) ------------------------------

    def add_amigos_upload(
        self,
        *,
        file_id: int,
        group_id: str,
        mime_type: str | None,
        size_bytes: int | None,
        created_by: str | None,
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO amigos_uploads (file_id, group_id, mime_type, size_bytes, created_by) "
            "VALUES (%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE group_id = VALUES(group_id), mime_type = VALUES(mime_type), "
            "size_bytes = VALUES(size_bytes)",
            (int(file_id), group_id, mime_type, size_bytes, created_by),
        )
        row = self.get_amigos_upload(file_id)
        assert row is not None
        return row

    def get_amigos_upload(self, file_id: int) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM amigos_uploads WHERE file_id = %s", (int(file_id),))
        return rows[0] if rows else None

    # --- «Los amigos»: agenda (MySQL) ----------------------------------------

    _ACTUACION_COLUMNS = (
        "title", "summary", "description", "image_url", "kind", "modality", "event_status",
        "starts_on", "starts_at", "ends_on", "ends_at", "timezone", "registration_deadline",
        "venue_name", "venue_address", "locality", "region", "country_code", "latitude",
        "longitude", "map_url", "organizer_name", "organizer_website", "event_url",
        "tickets_url", "price", "access_info", "public_contact", "organizer_group_id",
        "last_verified_on", "internal_notes", "weight", "source_email", "source_note",
    )

    def create_amigos_actuacion(
        self,
        *,
        actuacion_id: str,
        slug: str,
        editorial_status: str,
        author_user_id: str,
        fields: dict[str, object],
    ) -> dict[str, object]:
        cols = ["id", "slug", "editorial_status", "author_user_id"]
        vals: list[object] = [actuacion_id, slug, editorial_status, author_user_id]
        for key in self._ACTUACION_COLUMNS:
            if key in fields:
                cols.append(key)
                vals.append(fields[key])
        placeholders = ",".join(["%s"] * len(cols))
        self._run(
            f"INSERT INTO amigos_actuaciones ({','.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
        row = self.get_amigos_actuacion(actuacion_id)
        assert row is not None
        return row

    def get_amigos_actuacion(self, actuacion_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM amigos_actuaciones WHERE id = %s", (actuacion_id,))
        return rows[0] if rows else None

    def get_amigos_actuacion_by_slug(self, slug: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM amigos_actuaciones WHERE slug = %s", (slug,))
        return rows[0] if rows else None

    def update_amigos_actuacion(self, actuacion_id: str, **changes: object) -> dict[str, object] | None:
        fields = [k for k in changes if k in self._ACTUACION_COLUMNS]
        if fields:
            assignments = ", ".join(f"{k} = %s" for k in fields)
            self._run(
                f"UPDATE amigos_actuaciones SET {assignments} WHERE id = %s",
                (*[changes[k] for k in fields], actuacion_id),
            )
        return self.get_amigos_actuacion(actuacion_id)

    def set_amigos_actuacion_status(
        self,
        *,
        actuacion_id: str,
        editorial_status: str,
        published_at: str | None,
        reviewed_by: str | None,
        review_note: str | None,
    ) -> dict[str, object] | None:
        self._run(
            "UPDATE amigos_actuaciones SET editorial_status = %s, review_note = %s, "
            "reviewed_by = COALESCE(%s, reviewed_by), "
            "reviewed_at = CASE WHEN %s IS NULL THEN reviewed_at ELSE NOW(6) END, "
            "published_at = %s WHERE id = %s",
            (editorial_status, review_note, reviewed_by, reviewed_by, published_at, actuacion_id),
        )
        return self.get_amigos_actuacion(actuacion_id)

    def list_amigos_actuaciones(
        self,
        *,
        editorial_statuses: list[str] | None,
        from_date: str | None,
        to_date: str | None,
        kind: str | None,
        locality: str | None,
        group_id: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        clauses: list[str] = []
        args: list[object] = []
        if editorial_statuses is not None:
            if not editorial_statuses:
                return [], 0
            placeholders = ",".join(["%s"] * len(editorial_statuses))
            clauses.append(f"editorial_status IN ({placeholders})")
            args.extend(editorial_statuses)
        if from_date is not None:
            clauses.append("starts_on >= %s")
            args.append(from_date)
        if to_date is not None:
            clauses.append("starts_on <= %s")
            args.append(to_date)
        if kind is not None:
            clauses.append("kind = %s")
            args.append(kind)
        if locality is not None:
            clauses.append("LOWER(locality) = %s")
            args.append(locality.lower())
        if group_id is not None:
            clauses.append(
                "id IN (SELECT actuacion_id FROM amigos_actuacion_groups WHERE group_id = %s)"
            )
            args.append(group_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total_rows = self._run(f"SELECT COUNT(*) AS n FROM amigos_actuaciones {where}", tuple(args))
        total = int(str(total_rows[0]["n"])) if total_rows else 0
        rows = self._run(
            f"SELECT * FROM amigos_actuaciones {where} "
            "ORDER BY weight DESC, starts_on DESC, starts_at DESC LIMIT %s OFFSET %s",
            (*args, limit, offset),
        )
        return rows, total

    def increment_amigos_actuacion_counter(self, actuacion_id: str, field: str) -> int | None:
        if field not in ("views", "expands", "buys"):
            return None
        rows = self._run(
            f"UPDATE amigos_actuaciones SET {field} = {field} + 1 WHERE id = %s", (actuacion_id,)
        )
        _ = rows
        current = self._run(
            f"SELECT {field} AS n FROM amigos_actuaciones WHERE id = %s", (actuacion_id,)
        )
        if not current:
            return None
        return int(str(current[0]["n"]))

    def replace_amigos_actuacion_groups(
        self, actuacion_id: str, items: list[dict[str, object]]
    ) -> None:
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM amigos_actuacion_groups WHERE actuacion_id = %s", (actuacion_id,)
                )
                for item in items:
                    cur.execute(
                        "INSERT INTO amigos_actuacion_groups (actuacion_id, group_id, role) "
                        "VALUES (%s,%s,%s)",
                        (actuacion_id, item.get("group_id"), item.get("role") or "participant"),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_amigos_actuacion_groups(self, actuacion_id: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM amigos_actuacion_groups WHERE actuacion_id = %s ORDER BY role, group_id",
            (actuacion_id,),
        )

    # --- «Los amigos»: autorizaciones editoriales (MySQL) --------------------

    def set_amigos_authorization(
        self, *, user_id: str, scope: str, direct_publish: bool, granted_by: str | None
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO amigos_authorizations (user_id, scope, direct_publish, granted_by) "
            "VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
            "direct_publish = VALUES(direct_publish), granted_by = VALUES(granted_by)",
            (user_id, scope, 1 if direct_publish else 0, granted_by),
        )
        row = self.get_amigos_authorization(scope, user_id)
        assert row is not None
        return row

    def get_amigos_authorization(self, scope: str, user_id: str) -> dict[str, object] | None:
        rows = self._run(
            "SELECT * FROM amigos_authorizations WHERE scope = %s AND user_id = %s",
            (scope, user_id),
        )
        return rows[0] if rows else None

    def list_amigos_authorizations(self, scope: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM amigos_authorizations WHERE scope = %s ORDER BY user_id", (scope,)
        )

    def delete_amigos_authorization(self, scope: str, user_id: str) -> None:
        self._run(
            "DELETE FROM amigos_authorizations WHERE scope = %s AND user_id = %s", (scope, user_id)
        )

    # --- «Los amigos»: membresias (MySQL) ------------------------------------

    def set_amigos_member(
        self, *, group_id: str, user_id: str, role: str, status: str, granted_by: str | None
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO amigos_members (group_id, user_id, role, status, granted_by) "
            "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE role = VALUES(role), "
            "status = VALUES(status), granted_by = VALUES(granted_by)",
            (group_id, user_id, role, status, granted_by),
        )
        row = self.get_amigos_member(group_id, user_id)
        assert row is not None
        return row

    def get_amigos_member(self, group_id: str, user_id: str) -> dict[str, object] | None:
        rows = self._run(
            "SELECT * FROM amigos_members WHERE group_id = %s AND user_id = %s", (group_id, user_id)
        )
        return rows[0] if rows else None

    def list_amigos_members(self, group_id: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM amigos_members WHERE group_id = %s ORDER BY role, user_id", (group_id,)
        )

    def list_amigos_memberships_by_user(self, user_id: str) -> list[dict[str, object]]:
        return self._run("SELECT * FROM amigos_members WHERE user_id = %s", (user_id,))

    # --- «Los amigos»: articulos (MySQL) -------------------------------------

    def create_amigos_article(
        self,
        *,
        article_id: str,
        group_id: str,
        title: str,
        slug: str,
        event_date: str,
        summary: str | None,
        body: str,
        cover_url: str | None,
        author_user_id: str,
        status: str,
        scope: str = "group",
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO amigos_articles (id, group_id, scope, title, slug, event_date, summary, "
            "body, cover_url, author_user_id, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (article_id, group_id, scope, title, slug, event_date, summary, body, cover_url,
             author_user_id, status),
        )
        row = self.get_amigos_article(article_id)
        assert row is not None
        return row

    def get_amigos_article(self, article_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM amigos_articles WHERE id = %s", (article_id,))
        return rows[0] if rows else None

    def get_amigos_article_by_slug(self, group_id: str, slug: str) -> dict[str, object] | None:
        rows = self._run(
            "SELECT * FROM amigos_articles WHERE group_id = %s AND slug = %s", (group_id, slug)
        )
        return rows[0] if rows else None

    def get_amigos_article_by_scope_slug(self, scope: str, slug: str) -> dict[str, object] | None:
        rows = self._run(
            "SELECT * FROM amigos_articles WHERE scope = %s AND slug = %s", (scope, slug)
        )
        return rows[0] if rows else None

    def update_amigos_article(self, article_id: str, **changes: object) -> dict[str, object] | None:
        allowed = {"title", "event_date", "summary", "body", "cover_url", "slug"}
        fields = [k for k in changes if k in allowed]
        if fields:
            assignments = ", ".join(f"{k} = %s" for k in fields)
            self._run(
                f"UPDATE amigos_articles SET {assignments} WHERE id = %s",
                (*[changes[k] for k in fields], article_id),
            )
        return self.get_amigos_article(article_id)

    def set_amigos_article_status(
        self,
        *,
        article_id: str,
        status: str,
        reviewed_by: str | None,
        review_note: str | None,
        published_at: str | None,
    ) -> dict[str, object] | None:
        self._run(
            "UPDATE amigos_articles SET status = %s, review_note = %s, "
            "reviewed_by = COALESCE(%s, reviewed_by), "
            "reviewed_at = CASE WHEN %s IS NULL THEN reviewed_at ELSE NOW(6) END, "
            "published_at = %s WHERE id = %s",
            (status, review_note, reviewed_by, reviewed_by, published_at, article_id),
        )
        return self.get_amigos_article(article_id)

    def list_amigos_articles(
        self,
        *,
        group_id: str | None,
        group_ids: list[str] | None = None,
        statuses: list[str] | None,
        scope: str | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        clauses: list[str] = []
        args: list[object] = []
        if group_id is not None:
            clauses.append("group_id = %s")
            args.append(group_id)
        if scope is not None:
            clauses.append("scope = %s")
            args.append(scope)
        if group_ids is not None:
            if not group_ids:
                return [], 0
            placeholders = ",".join(["%s"] * len(group_ids))
            clauses.append(f"group_id IN ({placeholders})")
            args.extend(group_ids)
        if statuses is not None:
            placeholders = ",".join(["%s"] * len(statuses))
            clauses.append(f"status IN ({placeholders})")
            args.extend(statuses)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total_rows = self._run(f"SELECT COUNT(*) AS n FROM amigos_articles {where}", tuple(args))
        total = int(str(total_rows[0]["n"])) if total_rows else 0
        rows = self._run(
            f"SELECT * FROM amigos_articles {where} "
            "ORDER BY event_date DESC, created_at DESC LIMIT %s OFFSET %s",
            (*args, limit, offset),
        )
        return rows, total

    def list_amigos_articles_by_author(
        self, author_user_id: str, *, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        total_rows = self._run(
            "SELECT COUNT(*) AS n FROM amigos_articles WHERE author_user_id = %s",
            (author_user_id,),
        )
        total = int(str(total_rows[0]["n"])) if total_rows else 0
        rows = self._run(
            "SELECT * FROM amigos_articles WHERE author_user_id = %s "
            "ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (author_user_id, limit, offset),
        )
        return rows, total

    # --- «Los amigos»: recursos (MySQL) --------------------------------------

    def replace_amigos_media(self, article_id: str, items: list[dict[str, object]]) -> None:
        # Borrado + inserciones en UNA transacción: si algo falla a mitad, no se pierden
        # los recursos previos del artículo (rollback).
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM amigos_media WHERE article_id = %s", (article_id,))
                for item in items:
                    cur.execute(
                        "INSERT INTO amigos_media (article_id, kind, url, provider, video_id, "
                        "caption, credit, position) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (article_id, item.get("kind"), item.get("url"), item.get("provider"),
                         item.get("video_id"), item.get("caption"), item.get("credit"),
                         int(str(item.get("position") or 0))),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_amigos_media(self, article_id: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM amigos_media WHERE article_id = %s ORDER BY position, id", (article_id,)
        )

    # --- «Los amigos»: auditoria (MySQL) -------------------------------------

    def add_amigos_event(
        self,
        *,
        group_id: str | None,
        article_id: str | None,
        event_type: str,
        actor: str | None,
        from_status: str | None = None,
        to_status: str | None = None,
        detail_json: str | None = None,
    ) -> dict[str, object]:
        self._run(
            "INSERT INTO amigos_events (group_id, article_id, event_type, actor, from_status, "
            "to_status, detail_json) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (group_id, article_id, event_type, actor, from_status, to_status, detail_json),
        )
        rows = self._run("SELECT * FROM amigos_events ORDER BY id DESC LIMIT 1")
        assert rows
        return rows[0]

    def list_amigos_events(
        self, *, group_id: str | None, article_id: str | None
    ) -> list[dict[str, object]]:
        clauses: list[str] = []
        args: list[object] = []
        if group_id is not None:
            clauses.append("group_id = %s")
            args.append(group_id)
        if article_id is not None:
            clauses.append("article_id = %s")
            args.append(article_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._run(f"SELECT * FROM amigos_events {where} ORDER BY id", tuple(args))


    # --- «Los amigos»: ficha de coral (MySQL) --------------------------------

    _CORAL_FIELDS = (
        "foundation_date", "dissolution_date", "locality", "region", "country_code",
        "venue", "formation_type", "member_count", "website", "public_email",
        "director_person_id", "director_label", "linked_entity",
    )

    def _ensure_amigos_coral_row(self, group_id: str) -> None:
        self._run(
            "INSERT INTO amigos_coral_details (group_id) VALUES (%s) "
            "ON DUPLICATE KEY UPDATE group_id = group_id",
            (group_id,),
        )

    def get_amigos_coral_details(self, group_id: str) -> dict[str, object] | None:
        rows = self._run("SELECT * FROM amigos_coral_details WHERE group_id = %s", (group_id,))
        return rows[0] if rows else None

    def upsert_amigos_coral_details(self, group_id: str, **fields: object) -> dict[str, object]:
        self._ensure_amigos_coral_row(group_id)
        cols = [k for k in fields if k in self._CORAL_FIELDS]
        if cols:
            assignments = ", ".join(f"{k} = %s" for k in cols)
            self._run(
                f"UPDATE amigos_coral_details SET {assignments} WHERE group_id = %s",
                (*[fields[k] for k in cols], group_id),
            )
        row = self.get_amigos_coral_details(group_id)
        assert row is not None
        return row

    def replace_amigos_coral_attributes(
        self, group_id: str, items: list[dict[str, object]]
    ) -> None:
        self._ensure_amigos_coral_row(group_id)
        conn = self._conn()
        try:
            conn.autocommit(False)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM amigos_coral_attributes WHERE group_id = %s", (group_id,))
                for item in items:
                    cur.execute(
                        "INSERT INTO amigos_coral_attributes (group_id, facet, value, position) "
                        "VALUES (%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE position = VALUES(position)",
                        (group_id, item.get("facet"), item.get("value"),
                         int(str(item.get("position") or 0))),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_amigos_coral_attributes(self, group_id: str) -> list[dict[str, object]]:
        return self._run(
            "SELECT * FROM amigos_coral_attributes WHERE group_id = %s "
            "ORDER BY facet, position, id",
            (group_id,),
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


