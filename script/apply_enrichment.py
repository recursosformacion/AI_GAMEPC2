#!/usr/bin/env python
"""Aplica candidatos de enriquecimiento (personas) al catálogo, solo rellenando vacíos.

Resumen: lee `enrichment_candidates` (osap_api), y para personas actualiza en
`osap_storage.persons` únicamente los campos vacíos (birth_year, death_year, image).
Registra cada cambio en `enrichment_applied` (auditoría/reversión). Dry-run por defecto.

Uso:
    python script/apply_enrichment.py --limit 200
    python script/apply_enrichment.py --limit 200 --apply \
        --db-user osap2027 --db-password *** --storage-name osap_storage --stage-name osap_api
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymysql  # noqa: E402
from pymysql.cursors import DictCursor  # noqa: E402

_FIELD_MAP = {
    "birth_year": "persons_birth_year",
    "death_year": "persons_death_year",
    "image": "persons_image_url",
}

_READ = """
SELECT entity_key, field, value, source, confidence
FROM enrichment_candidates
WHERE entity_type = 'person' AND status = 'new'
  AND field IN ('birth_year', 'death_year', 'image')
ORDER BY entity_key, field, confidence DESC
"""

_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS enrichment_applied (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entity_type VARCHAR(16) NOT NULL,
  entity_key VARCHAR(255) NOT NULL,
  field VARCHAR(64) NOT NULL,
  old_value TEXT NULL,
  new_value TEXT NOT NULL,
  source VARCHAR(32) NOT NULL,
  applied_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_applied_entity (entity_type, entity_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def _connect(host: str, port: int, user: str, password: str, database: str) -> Any:
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def _blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db-host", default=os.environ.get("OSAP_DB_HOST", "127.0.0.1"))
    ap.add_argument("--db-port", type=int, default=int(os.environ.get("OSAP_DB_PORT", "3306")))
    ap.add_argument("--db-user", default=os.environ.get("OSAP_DB_USER", ""))
    ap.add_argument("--db-password", default=os.environ.get("OSAP_DB_PASSWORD", ""))
    ap.add_argument("--storage-name", default="osap_storage")
    ap.add_argument("--stage-name", default="osap_api")
    args = ap.parse_args()
    if not args.db_user:
        ap.error("falta usuario de BD (OSAP_DB_USER o --db-user)")

    stage = _connect(args.db_host, args.db_port, args.db_user, args.db_password, args.stage_name)
    storage = _connect(args.db_host, args.db_port, args.db_user, args.db_password, args.storage_name)
    try:
        with stage.cursor() as cur:
            cur.execute(_READ)
            rows = list(cur.fetchall())

        best: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (str(row["entity_key"]), str(row["field"]))
            if key not in best:
                best[key] = row

        changes: list[dict[str, Any]] = []
        for (entity_key, field), row in best.items():
            column = _FIELD_MAP.get(field)
            if column is None:
                continue
            with storage.cursor() as cur:
                cur.execute(f"SELECT {column} AS current FROM persons WHERE persons_id=%s", (entity_key,))
                found = cur.fetchone()
            if not found or not _blank(found["current"]):
                continue
            changes.append(
                {
                    "entity_key": entity_key,
                    "field": field,
                    "column": column,
                    "old": found["current"],
                    "new": str(row["value"]),
                    "source": str(row["source"]),
                }
            )
            if len(changes) >= args.limit:
                break

        by_field: dict[str, int] = {}
        for change in changes:
            by_field[change["field"]] = by_field.get(change["field"], 0) + 1
        print(f"candidatos_leidos={len(rows)} cambios_propuestos={len(changes)}")
        for field, count in sorted(by_field.items()):
            print(f"  {field}: {count}")

        if not args.apply:
            print("DRY-RUN (usa --apply para escribir en osap_storage)")
            return 0

        with stage.cursor() as cur:
            cur.execute(_AUDIT_DDL)
        stage.commit()
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        applied = 0
        for change in changes:
            with storage.cursor() as cur:
                cur.execute(
                    f"UPDATE persons SET {change['column']}=%s "
                    f"WHERE persons_id=%s AND ({change['column']} IS NULL OR {change['column']}='')",
                    (change["new"], change["entity_key"]),
                )
                if cur.rowcount < 1:
                    continue
            with stage.cursor() as cur:
                cur.execute(
                    "INSERT INTO enrichment_applied "
                    "(entity_type, entity_key, field, old_value, new_value, source, applied_at) "
                    "VALUES ('person', %s, %s, %s, %s, %s, %s)",
                    (change["entity_key"], change["field"], change["old"], change["new"],
                     change["source"], now),
                )
            applied += 1
        storage.commit()
        stage.commit()
        print(f"aplicados={applied}")
        return 0
    finally:
        storage.close()
        stage.close()


if __name__ == "__main__":
    raise SystemExit(main())
