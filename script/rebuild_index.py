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
    ap.add_argument("--full", action="store_true", help="vaciado previo + reindexado completo")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--user", default="osap2027")
    ap.add_argument("--password", default="2027osapdb")
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

    conn = pymysql.connect(host=args.host, user=args.user, password=args.password,
                           database=args.database, charset="utf8mb4", autocommit=True)
    if args.full:
        with conn.cursor() as cur:
            for tbl in ("index_works", "index_representations", "index_work_voicings"):
                cur.execute(f"TRUNCATE TABLE {tbl}")
                print("vaciada", tbl)
    conn.close()

    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    cmd = [sys.executable, str(ROOT / "script" / "index_works.py"),
           "--providers", args.providers,
           "--db-host", args.host,
           "--db-user", args.user,
           "--db-password", args.password,
           "--db-api", args.db_api,
           "--db-omr", args.db_omr]
    print("indexando:", args.providers)
    rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
    if rc != 0:
        print("index_works.py falló; código", rc)
        return rc

    conn = pymysql.connect(host=args.host, user=args.user, password=args.password,
                           database=args.database, charset="utf8mb4", autocommit=True)
    with conn.cursor() as cur:
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
               "--password", args.password, "--database", args.database]
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
