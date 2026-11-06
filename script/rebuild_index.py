#!/usr/bin/env python
"""Reconstruye/actualiza el índice local de osap-api (procedimiento oficial de reindexado).

No toca el esquema (eso es `migrate_index_schema.py`); solo datos derivados.

- `--full`: vacía `index_works`/`index_representations`/`index_work_voicings` y reindexa.
- Sin `--full` (incremental): upsert idempotente, no borra nada.
- Al final limpia huérfanos de `index_work_voicings`.
- `--indexnow`: tras reindexar, notifica a IndexNow las obras recientes (paso final del
  reindexado; best-effort, no aborta el job). Ver `script/indexnow.py`.

Un rebuild es reproducible: el índice se deriva de los proveedores + la autoridad
(`persons` en osap-storage). Añadir ficheros = relanzar este job (o el incremental).

Uso (desde osap-api):
    python script/rebuild_index.py --providers omr,cpdl
    python script/rebuild_index.py --full --providers omr,cpdl,imslp,mutopia,musicbrainz
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--providers", default="omr,cpdl")
    ap.add_argument("--limit", type=int, default=0, help="límite de obras para pruebas (0 = todas)")
    ap.add_argument("--full", action="store_true", help="vaciado previo + reindexado completo")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--user", default="osap2027")
    ap.add_argument("--password", default=os.environ.get("OSAP_INDEX_DB_PASSWORD", ""))
    ap.add_argument("--database", default="osap-api")
    ap.add_argument("--db-omr", default="osap-storage", help="BD de osap-storage (lectura)")
    ap.add_argument("--db-api", default="osap-api", help="BD de osap-api (índice)")
    ap.add_argument("--indexnow", action="store_true",
                    help="tras reindexar, notifica a IndexNow las obras recientes (best-effort)")
    ap.add_argument("--indexnow-days", type=int, default=7, help="ventana de recencia de IndexNow")
    ap.add_argument("--indexnow-base", default=os.environ.get("OSAP_PUBLIC_BASE_URL", ""),
                    help="base pública para IndexNow (por defecto OSAP_PUBLIC_BASE_URL)")
    ap.add_argument("--indexnow-key", default=os.environ.get("INDEXNOW_KEY", ""),
                    help="clave de IndexNow (por defecto INDEXNOW_KEY)")
    args = ap.parse_args()

    lock_conn = pymysql.connect(host=args.host, user=args.user, password=args.password,
                                database=args.database, charset="utf8mb4", autocommit=True)
    with lock_conn.cursor() as lock_cur:
        lock_cur.execute("SELECT GET_LOCK('osap_index_jobs', 0) AS got")
        if not lock_cur.fetchone()[0]:
            print("otro job de índice está en ejecución; salgo")
            return 75
    conn = pymysql.connect(host=args.host, user=args.user, password=args.password,
                           database=args.database, charset="utf8mb4", autocommit=True)
    if args.full:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS index_id_aliases ("
                " old_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,"
                " new_id BIGINT UNSIGNED NOT NULL,"
                " method VARCHAR(32) NOT NULL,"
                " updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                "   ON UPDATE CURRENT_TIMESTAMP,"
                " KEY ix_index_id_aliases_new (new_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
            # Preserve source identities across the destructive rebuild. This
            # snapshot is only for the mapping; the public ID is never inferred
            # from the title.
            cur.execute("DROP TABLE IF EXISTS index_rebuild_old_reps")
            cur.execute(
                "CREATE TABLE index_rebuild_old_reps AS "
                "SELECT work_id, provider, source_rep_id, resource_id "
                "FROM index_representations WHERE source_rep_id <> ''"
            )
            for tbl in ("index_works", "index_representations", "index_work_voicings"):
                cur.execute(f"TRUNCATE TABLE {tbl}")
                print("vaciada", tbl)
    conn.close()

    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "OSAP_INDEX_DB_PASSWORD": args.password,
    }
    cmd = [sys.executable, str(ROOT / "script" / "index_works.py"),
           "--providers", args.providers,
           "--db-host", args.host,
           "--db-user", args.user,
           "--db-api", args.db_api,
           "--db-omr", args.db_omr,
           "--limit", str(args.limit)]
    print("indexando:", args.providers)
    rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
    if rc != 0:
        print("index_works.py falló; código", rc)
        return rc

    conn = pymysql.connect(host=args.host, user=args.user, password=args.password,
                           database=args.database, charset="utf8mb4", autocommit=True)
    with conn.cursor() as cur:
        if args.full:
            cur.execute(
                "INSERT INTO index_id_aliases (old_id, new_id, method) "
                "SELECT o.work_id, MIN(n.work_id), 'source_rep' "
                "FROM index_rebuild_old_reps o "
                "JOIN index_representations n "
                "  ON n.provider = o.provider "
                " AND n.source_rep_id = o.source_rep_id "
                " AND n.source_rep_id <> '' "
                "GROUP BY o.work_id "
                "HAVING COUNT(DISTINCT n.work_id) = 1 "
                "ON DUPLICATE KEY UPDATE "
                " new_id=VALUES(new_id), method=VALUES(method), updated_at=NOW()"
            )
            print("mapping old_id->new_id generado:", cur.rowcount)
            cur.execute("DROP TABLE IF EXISTS index_rebuild_old_reps")
        cur.execute(
            "DELETE FROM index_work_voicings WHERE work_id NOT IN (SELECT id FROM index_works)"
        )
        print("huérfanos de voicing limpiados:", cur.rowcount)
    conn.close()
    print("reindexado completado")

    if args.indexnow:
        cmd = [sys.executable, str(ROOT / "script" / "indexnow.py"),
               "--days", str(args.indexnow_days),
               "--host", args.host, "--user", args.user,
               "--database", args.database]
        if args.indexnow_base:
            cmd += ["--base", args.indexnow_base]
        if args.indexnow_key:
            cmd += ["--key", args.indexnow_key]
        rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
        if rc != 0:
            print("indexnow.py falló (best-effort); código", rc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
