#!/usr/bin/env python
"""Reconstruye/actualiza el índice local de osap-api (procedimiento oficial de reindexado).

No toca el esquema (eso es `migrate_index_schema.py`); solo datos derivados.

- `--full`: vacía `index_works`/`index_representations`/`index_work_voicings` y reindexa.
- Sin `--full` (incremental): upsert idempotente, no borra nada.
- Al final limpia huérfanos de `index_work_voicings`.

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
           "--providers", args.providers]
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
