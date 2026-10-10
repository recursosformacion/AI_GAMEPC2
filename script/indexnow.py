#!/usr/bin/env python
"""Notifica a IndexNow las URLs de obra actualizadas recientemente (paso final del reindexado).

Lee de `index_works` (BD de osap-api) las obras con `updated_at` en los últimos N días, las
publica como `{base}/obra/index-{id}/{slug}` usando la MISMA función canónica que el sitemap
(`work_canonical_slug`) y las envía a IndexNow en lotes de hasta 10.000. Es **best-effort**:
si IndexNow no responde, se registra pero NO se interrumpe el reindexado.

La clave y su fichero de verificación (`web/public/{key}.txt`, servido en `{base}/{key}.txt`)
deben existir. `--base`/`--key` (o `OSAP_PUBLIC_BASE_URL`/`INDEXNOW_KEY`) determinan el host
verificado.

Uso (desde osap-api, con PYTHONPATH=osap-api):
    python script/indexnow.py --days 7 --limit 10000
    python script/indexnow.py --base https://app.openmusicrepository.com --key osap-indexnow-2026
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.osap.api.seo.indexnow import indexnow_host, submit_urls  # noqa: E402
from src.osap.api.seo.slug import work_canonical_slug  # noqa: E402

DEFAULT_BASE = "https://app.openmusicrepository.com"
DEFAULT_KEY = "osap-indexnow-2026"


def _recent_work_urls(cur: pymysql.cursors.Cursor, base: str, days: int, limit: int) -> list[str]:
    """URLs canónicas de las obras con `updated_at` en los últimos `days` días."""
    cur.execute(
        """
        SELECT id, title FROM index_works
        WHERE updated_at >= NOW() - INTERVAL %s DAY
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (days, limit),
    )
    urls: list[str] = []
    for work_id, title in cur.fetchall():
        if not title:
            continue
        urls.append(f"{base}/obra/index-{int(work_id)}/{work_canonical_slug(str(title))}")
    return urls


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7, help="ventana de recencia (días)")
    ap.add_argument("--limit", type=int, default=10_000, help="máximo de URLs a enviar")
    ap.add_argument("--base", default=os.environ.get("OSAP_PUBLIC_BASE_URL", DEFAULT_BASE))
    ap.add_argument("--key", default=os.environ.get("INDEXNOW_KEY", DEFAULT_KEY))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--user", default="osap2027")
    ap.add_argument("--password", default="2027osapdb")
    ap.add_argument("--database", default="osap-api")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    conn = pymysql.connect(host=args.host, user=args.user, password=args.password,
                           database=args.database, charset="utf8mb4", autocommit=True)
    try:
        with conn.cursor() as cur:
            urls = _recent_work_urls(cur, base, args.days, args.limit)
    finally:
        conn.close()

    if not urls:
        print("indexnow: nada que enviar (0 URLs recientes)")
        return 0

    codes = submit_urls(urls, host=indexnow_host(base), key=args.key, base_url=base)
    ok = sum(1 for code in codes if code in (200, 202))
    print(f"indexnow: {len(urls)} URLs en {len(codes)} lote(s); ok={ok} códigos={codes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
