#!/usr/bin/env python
"""Prepara (NO ejecuta por defecto) el esquema de **aportaciones** de osap-api.

Crea, de forma idempotente, las cuatro tablas del modelo de aportación:
`contributions`, `contribution_relations`, `contribution_events`, `contribution_artifacts`.

Características:
- `CREATE TABLE IF NOT EXISTS` (repetible; no hace ALTER ni toca datos).
- **FKs solo dentro de osap-api** (relaciones/eventos/artefactos → contributions).
  `contribution_artifacts.file_id` es un id opaco de osap-storage: **sin FK cross-service**.
- **Sin `representation_id`** ni cambios de impacto: eso va en su propia migración.
- `--dry-run` imprime el plan y el DDL sin ejecutar nada.
- Comprobación previa (qué tablas existen ya) y posterior (tablas + FKs creadas).

Uso (desde osap-api):
    # Ver qué haría, sin tocar la BD (recomendado para revisión):
    PYTHONPATH=<osap-api> python script/migrate_contributions_schema.py --dry-run

    # Aplicar (solo cuando se autorice; NO ejecutar en Dev/Prod todavía):
    PYTHONPATH=<osap-api> python script/migrate_contributions_schema.py

Referencia de diseño: `_docs/aportaciones-esquema.md` y
`docs/osap/contributions-migration.md`.
"""

# ruff: noqa: E501 — el DDL contiene líneas COMMENT largas a propósito (legibilidad SQL).

from __future__ import annotations

import argparse

import pymysql

# Orden de creación: `contributions` primero (las demás dependen por FK).
_TABLES: list[str] = [
    "contributions",
    "contribution_relations",
    "contribution_events",
    "contribution_artifacts",
]

_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS contributions (
      id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      actor_user_id   CHAR(36)        NOT NULL
        COMMENT 'osap-auth users.id (id opaco)',
      operation       VARCHAR(32)     NOT NULL
        COMMENT 'create_work|add_representation|add_resource (nucleo aditivo, cerrado)',
      target_kind     VARCHAR(16)     NOT NULL
        COMMENT 'work|representation|resource',
      target_id       VARCHAR(64)     DEFAULT NULL
        COMMENT 'id en osap-storage. Para add_resource = representation_id. El id de fichero NO va aqui (ver contribution_artifacts)',
      declared_source VARCHAR(512)    DEFAULT NULL
        COMMENT 'fuente declarada por el usuario',
      payload_json    LONGTEXT        DEFAULT NULL
        COMMENT 'metadatos declarados (create_work/add_representation): title/origin/type/license/source_name',
      status          VARCHAR(16)     NOT NULL DEFAULT 'draft'
        COMMENT 'draft|submitted|in_review|accepted|rejected|withdrawn',
      reviewed_by     VARCHAR(128)    DEFAULT NULL,
      reviewed_at     DATETIME(6)     DEFAULT NULL,
      review_note     VARCHAR(512)    DEFAULT NULL,
      created_at      DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at      DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      KEY idx_contrib_actor (actor_user_id),
      KEY idx_contrib_status (status),
      KEY idx_contrib_target (target_kind, target_id),
      KEY idx_contrib_actor_created (actor_user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS contribution_relations (
      id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      contribution_id   BIGINT UNSIGNED NOT NULL,
      relation_kind     VARCHAR(16)     NOT NULL
        COMMENT 'musical|contribution',
      relation_code     VARCHAR(32)     NOT NULL
        COMMENT 'musical: slug de roles; contribution: aportante|propietario_comparte|fuente_declarada',
      person_id         CHAR(36)        DEFAULT NULL
        COMMENT 'osap-storage persons_id (id opaco, sin FK)',
      person_name       VARCHAR(512)    DEFAULT NULL,
      validation_status VARCHAR(16)     NOT NULL DEFAULT 'pending'
        COMMENT 'pending|accepted|rejected (eje musical)',
      validated_by      VARCHAR(128)    DEFAULT NULL,
      validated_at      DATETIME(6)     DEFAULT NULL,
      materialized      TINYINT(1)      NOT NULL DEFAULT 0,
      created_at        DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at        DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      KEY idx_contribrel_contribution (contribution_id),
      KEY idx_contribrel_validation (relation_kind, validation_status),
      CONSTRAINT fk_contribrel_contribution FOREIGN KEY (contribution_id)
        REFERENCES contributions (id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS contribution_events (
      id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      contribution_id BIGINT UNSIGNED NOT NULL,
      event_type      VARCHAR(32)     NOT NULL
        COMMENT 'created|submitted|status_changed|relation_added|relation_removed|relation_validated|materialized|withdrawn|note',
      from_status     VARCHAR(16)     DEFAULT NULL,
      to_status       VARCHAR(16)     DEFAULT NULL,
      relation_id     BIGINT UNSIGNED DEFAULT NULL,
      detail_json     LONGTEXT        DEFAULT NULL,
      actor           VARCHAR(128)    DEFAULT NULL COMMENT 'user id o service:<id>',
      created_at      DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      KEY idx_contribev_contribution (contribution_id, created_at),
      CONSTRAINT fk_contribev_contribution FOREIGN KEY (contribution_id)
        REFERENCES contributions (id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS contribution_artifacts (
      id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      contribution_id BIGINT UNSIGNED NOT NULL,
      file_id         BIGINT UNSIGNED NOT NULL
        COMMENT 'osap-storage files.id (id opaco, SIN FK cross-service)',
      kind            VARCHAR(32)     DEFAULT NULL COMMENT 'score|audio|other',
      created_at      DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (id),
      KEY idx_contribart_contribution (contribution_id),
      KEY idx_contribart_file (file_id),
      CONSTRAINT fk_contribart_contribution FOREIGN KEY (contribution_id)
        REFERENCES contributions (id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


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
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN "
            "('contributions','contribution_relations','contribution_events','contribution_artifacts')"
        )
        return {row[0] for row in cur.fetchall()}


def _fk_counts(conn: pymysql.connections.Connection) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME, COUNT(*) FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL "
            "AND TABLE_NAME IN "
            "('contribution_relations','contribution_events','contribution_artifacts') "
            "GROUP BY TABLE_NAME"
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
        print("[dry-run] No se ha modificado la base de datos.")
        return 0

    conn = _connect(args)
    try:
        before = _existing_tables(conn)
        print(f"tablas ya existentes (se omitirán): {sorted(before) or 'ninguna'}")
        for stmt in _DDL:
            with conn.cursor() as cur:
                cur.execute(stmt)

        # ALTER idempotente: `payload_json` (tablas creadas antes de esta columna).
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'contributions' "
                "AND column_name = 'payload_json'"
            )
            row = cur.fetchone()
            if row is not None and int(str(row[0])) == 0:
                cur.execute(
                    "ALTER TABLE contributions ADD COLUMN payload_json LONGTEXT DEFAULT NULL "
                    "AFTER declared_source"
                )
                print("ALTER: contributions.payload_json añadida")

        after = _existing_tables(conn)
        missing = [t for t in _TABLES if t not in after]
        fks = _fk_counts(conn)
        print(f"tablas presentes: {sorted(after)}")
        for table, expected in (
            ("contribution_relations", 1),
            ("contribution_events", 1),
            ("contribution_artifacts", 1),
        ):
            got = fks.get(table, 0)
            ok = "OK" if got == expected else "REVISAR"
            print(f"FK {table}: {got} (esperado {expected}) [{ok}]")
        if missing:
            print(f"ERROR: faltan tablas: {missing}")
            return 1
        print(f"esquema de aportaciones aplicado (idempotente): {args.database}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
