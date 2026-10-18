#!/usr/bin/env python
"""Crea una notificación en la campana de la app (bandeja de `notifications`).

Sin `--user` es un aviso **global**: se muestra a los administradores (el job de reindexado
lo usa para pedir el reenvío del sitemap). Con `--user <uuid>` es un aviso personal.

Uso:
    python script/notify.py --kind sitemap_resubmit \
        --title "Reindexación completada" \
        --body "Reenvía el sitemap en Search Console." \
        --link https://app.openmusicrepository.com/sitemap.xml \
        --host 127.0.0.1 --user U --password P --database osap_api

Las credenciales del job vienen de `OSAP_INDEX_DB_*` en su `EnvironmentFile`.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

import pymysql


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--link", default=None)
    parser.add_argument("--user", default=None, help="UUID del destinatario (vacío = global)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap_api")
    parser.add_argument("--password", default="")
    parser.add_argument("--database", default="osap_api")
    args = parser.parse_args()

    created_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    conn = pymysql.connect(
        host=args.host,
        user=args.db_user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notifications (user_id, kind, title, body, link, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (args.user, args.kind, args.title, args.body, args.link, created_at),
            )
            print(f"notificación creada: id={cur.lastrowid} kind={args.kind}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
