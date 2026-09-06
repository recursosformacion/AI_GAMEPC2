#!/usr/bin/env python
"""Limpia CPDL del índice local de osap-api (`index_representations`/`index_works`).

Desde que CPDL es un provider VIVO sobre su corpus (cpdl_pages/cpdl_voicings de
osap-storage), el índice local ya no debe contener copias CPDL: duplicarían cada
página en los resultados. Este script elimina las representaciones provider='cpdl'
y las filas de `index_works` que quedan huérfanas (sin ninguna representación).
Idempotente: ejecutarlo dos veces no cambia nada.

Uso (en osap-api, con PYTHONPATH=osap-api):
    python script/drop_cpdl_index_rows.py
    python script/drop_cpdl_index_rows.py --db-name osap-api
"""

from __future__ import annotations

import argparse

import pymysql


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-name", default="osap-api")
    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.db_host,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM index_representations WHERE provider = 'cpdl'")
            reps_deleted = cur.rowcount
            # Huérfanas del índice: sin representaciones de ningún provider.
            cur.execute(
                "DELETE FROM index_works WHERE NOT EXISTS ("
                "SELECT 1 FROM index_representations r WHERE r.work_id = index_works.id)"
            )
            works_deleted = cur.rowcount
        conn.commit()
    print(f"representaciones cpdl eliminadas: {reps_deleted}")
    print(f"filas index_works huérfanas eliminadas: {works_deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
