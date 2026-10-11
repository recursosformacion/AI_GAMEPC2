#!/usr/bin/env python
"""Prepara (NO ejecuta por defecto) el esquema de «Los amigos» de osap-api.

Crea de forma idempotente las cinco tablas del miniblog de grupos musicales:
`amigos_groups`, `amigos_members`, `amigos_articles`, `amigos_media`, `amigos_events`.

Características:
- `CREATE TABLE IF NOT EXISTS` (aditivo y repetible; no hace ALTER ni toca datos).
- FKs SOLO dentro de osap-api (miembros/artículos → groups; media → articles).
- `--dry-run` imprime el plan y el DDL sin ejecutar nada.
- Comprobación previa (qué tablas existen) y posterior (tablas + FKs creadas).

Uso (desde osap-api):
    # Ver qué haría, sin tocar la BD:
    PYTHONPATH=<osap-api> python script/migrate_amigos_schema.py --dry-run

    # Aplicar (solo cuando se autorice):
    PYTHONPATH=<osap-api> python script/migrate_amigos_schema.py

Referencia de diseño: `docs/osap/amigos.md`.
"""

from __future__ import annotations

import argparse

import pymysql

_TABLES: list[str] = [
    "amigos_groups",
    "amigos_members",
    "amigos_articles",
    "amigos_media",
    "amigos_events",
    "amigos_coral_details",
    "amigos_coral_attributes",
    "amigos_group_links",
    "amigos_uploads",
]

# Columnas comunes añadidas a tablas ya existentes (idempotente, comprobando
# information_schema; compatible MySQL 8 y MariaDB).
_COLUMNS: list[tuple[str, str, str]] = [
    ("amigos_groups", "website", "VARCHAR(1024) NULL"),
    ("amigos_groups", "email", "VARCHAR(254) NULL"),
    ("amigos_groups", "logo_url", "VARCHAR(1024) NULL"),
]

_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS amigos_groups (
      id             CHAR(32)      NOT NULL,
      slug           VARCHAR(96)   NOT NULL,
      name           VARCHAR(255)  NOT NULL,
      kind           VARCHAR(32)   NOT NULL DEFAULT 'coral',
      description    TEXT,
      image_url      VARCHAR(1024),
      website        VARCHAR(1024),
      email          VARCHAR(254),
      logo_url       VARCHAR(1024),
      status         VARCHAR(16)   NOT NULL DEFAULT 'active',
      editorial_mode VARCHAR(16)   NOT NULL DEFAULT 'moderated'
        COMMENT 'direct|moderated (por grupo)',
      created_by     CHAR(36),
      created_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      UNIQUE KEY uq_amigos_group_slug (slug)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_members (
      group_id   CHAR(32)     NOT NULL,
      user_id    CHAR(36)     NOT NULL COMMENT 'osap-auth users.id (id opaco)',
      role       VARCHAR(16)  NOT NULL DEFAULT 'collaborator' COMMENT 'admin|collaborator',
      status     VARCHAR(16)  NOT NULL DEFAULT 'active' COMMENT 'active|revoked',
      granted_by CHAR(36),
      created_at DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (group_id, user_id),
      KEY idx_amigos_member_user (user_id),
      CONSTRAINT fk_amigos_member_group FOREIGN KEY (group_id)
        REFERENCES amigos_groups (id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_articles (
      id             CHAR(32)      NOT NULL,
      group_id       CHAR(32)      NOT NULL,
      title          VARCHAR(512)  NOT NULL,
      slug           VARCHAR(200)  NOT NULL,
      event_date     DATE          NOT NULL COMMENT 'fecha del evento (independiente de published_at)',
      summary        TEXT,
      body           LONGTEXT,
      cover_url      VARCHAR(1024),
      author_user_id CHAR(36)      NOT NULL COMMENT 'autor ORIGINAL (inmutable)',
      status         VARCHAR(16)   NOT NULL DEFAULT 'draft'
        COMMENT 'draft|pending|published|withdrawn',
      published_at   DATETIME(6),
      reviewed_by    CHAR(36),
      reviewed_at    DATETIME(6),
      review_note    VARCHAR(512),
      created_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      UNIQUE KEY uq_amigos_article_slug (group_id, slug),
      KEY idx_amigos_article_status (status),
      KEY idx_amigos_article_author (author_user_id),
      KEY idx_amigos_article_event (group_id, event_date),
      CONSTRAINT fk_amigos_article_group FOREIGN KEY (group_id)
        REFERENCES amigos_groups (id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_media (
      id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      article_id CHAR(32)        NOT NULL,
      kind       VARCHAR(16)     NOT NULL COMMENT 'video|photo',
      url        VARCHAR(1024)   NOT NULL,
      provider   VARCHAR(32)     COMMENT 'p. ej. youtube',
      video_id   VARCHAR(64)     COMMENT 'id del vídeo (para incrustar de forma segura)',
      caption    VARCHAR(512),
      credit     VARCHAR(512),
      position   INT             NOT NULL DEFAULT 0,
      created_at DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      KEY idx_amigos_media_article (article_id, position),
      CONSTRAINT fk_amigos_media_article FOREIGN KEY (article_id)
        REFERENCES amigos_articles (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_events (
      id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      group_id    CHAR(32),
      article_id  CHAR(32),
      event_type  VARCHAR(48)     NOT NULL,
      actor       CHAR(36),
      from_status VARCHAR(16),
      to_status   VARCHAR(16),
      detail_json LONGTEXT,
      created_at  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      KEY idx_amigos_event_group (group_id, created_at),
      KEY idx_amigos_event_article (article_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_coral_details (
      group_id          CHAR(32)     NOT NULL,
      foundation_date   DATE,
      dissolution_date  DATE,
      locality          VARCHAR(160),
      region            VARCHAR(160),
      country_code      CHAR(2),
      venue             VARCHAR(255),
      formation_type    VARCHAR(48)  COMMENT 'mixed|equal_voices|children|youth|male|female|other',
      member_count      INT,
      website           VARCHAR(1024),
      public_email      VARCHAR(254),
      director_person_id VARCHAR(64) COMMENT 'enlace opcional a una persona identificada',
      director_label    VARCHAR(255),
      linked_entity     VARCHAR(255),
      created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (group_id),
      CONSTRAINT fk_amigos_coral_group FOREIGN KEY (group_id)
        REFERENCES amigos_groups (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_coral_attributes (
      id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      group_id   CHAR(32)        NOT NULL,
      facet      VARCHAR(32)     NOT NULL COMMENT 'repertoire|language',
      value      VARCHAR(120)    NOT NULL,
      position   INT             NOT NULL DEFAULT 0,
      created_at DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      UNIQUE KEY uq_amigos_coral_attr (group_id, facet, value),
      KEY idx_amigos_coral_attr (group_id, facet, position),
      CONSTRAINT fk_amigos_coral_attr_group FOREIGN KEY (group_id)
        REFERENCES amigos_coral_details (group_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_group_links (
      id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      group_id   CHAR(32)        NOT NULL,
      kind       VARCHAR(32)     NOT NULL COMMENT 'facebook|instagram|other',
      label      VARCHAR(64),
      url        VARCHAR(1024)   NOT NULL,
      position   INT             NOT NULL DEFAULT 0,
      created_at DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      KEY idx_amigos_group_link (group_id, position),
      CONSTRAINT fk_amigos_group_link_group FOREIGN KEY (group_id)
        REFERENCES amigos_groups (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS amigos_uploads (
      file_id    BIGINT UNSIGNED NOT NULL,
      group_id   CHAR(32)        NOT NULL,
      mime_type  VARCHAR(64),
      size_bytes BIGINT UNSIGNED,
      created_by CHAR(36),
      created_at DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (file_id),
      KEY idx_amigos_upload_group (group_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]

_FK_TABLES = ("amigos_members", "amigos_articles", "amigos_media", "amigos_coral_details",
              "amigos_coral_attributes", "amigos_group_links")


def _connect(args: argparse.Namespace) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=args.host,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=True,
        ssl_disabled=args.host in ("127.0.0.1", "localhost"),
    )


def _existing_tables(conn: pymysql.connections.Connection) -> set[str]:
    placeholders = ",".join(["%s"] * len(_TABLES))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({placeholders})",
            _TABLES,
        )
        return {row[0] for row in cur.fetchall()}


def _fk_counts(conn: pymysql.connections.Connection) -> dict[str, int]:
    placeholders = ",".join(["%s"] * len(_FK_TABLES))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME, COUNT(*) FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL "
            f"AND TABLE_NAME IN ({placeholders}) GROUP BY TABLE_NAME",
            _FK_TABLES,
        )
        return {row[0]: int(row[1]) for row in cur.fetchall()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--user", default="osap2027")
    ap.add_argument("--password", default="2027osapdb")
    ap.add_argument("--database", default="osap-api")
    ap.add_argument("--dry-run", action="store_true", help="no ejecuta DDL; solo muestra el plan")
    args = ap.parse_args()

    if args.dry_run:
        print(f"[dry-run] BD objetivo: {args.database}@{args.host}")
        print("[dry-run] Se crearían (IF NOT EXISTS, idempotente):")
        for table in _TABLES:
            print(f"          - {table}")
        print("[dry-run] DDL:")
        for stmt in _DDL:
            print(stmt.strip())
        print("[dry-run] Columnas a asegurar (ALTER ADD COLUMN si faltan):")
        for table, column, ddl in _COLUMNS:
            print(f"          - {table}.{column} {ddl}")
        print("[dry-run] No se ha modificado la base de datos.")
        return 0

    conn = _connect(args)
    try:
        before = _existing_tables(conn)
        print(f"tablas ya existentes (se omitirán): {sorted(before) or 'ninguna'}")
        for stmt in _DDL:
            with conn.cursor() as cur:
                cur.execute(stmt)
        for table, column, ddl in _COLUMNS:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE "
                    "TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                    (table, column),
                )
                if cur.fetchone()[0] == 0:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
                    print(f"columna añadida: {table}.{column}")
        after = _existing_tables(conn)
        missing = [t for t in _TABLES if t not in after]
        fks = _fk_counts(conn)
        print(f"tablas presentes: {sorted(after)}")
        for table in _FK_TABLES:
            got = fks.get(table, 0)
            ok = "OK" if got >= 1 else "REVISAR"
            print(f"FK {table}: {got} [{ok}]")
        if missing:
            print(f"ERROR: faltan tablas: {missing}")
            return 1
        print(f"esquema de «Los amigos» aplicado (idempotente): {args.database}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
