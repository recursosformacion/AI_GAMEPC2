#!/usr/bin/env python
"""Backfill stable source ids for IMSLP/Mutopia representations.

IMSLP has no numeric work id in its Worklist API; Mutopia resources are remote and
only expose their download URL. Both use `provider:sha1(canonical_url)` as their
representation identity so old and new index rows are idempotent.

Usage:
    python script/backfill_source_ids.py --database osap_api
    python script/backfill_source_ids.py --database osap_api --dry-run
"""

from __future__ import annotations

import argparse

import pymysql

PROVIDERS = ("imslp", "mutopia")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--user", default="osap2027")
    parser.add_argument("--password", default="2027osapdb")
    parser.add_argument("--database", default="osap_api")
    parser.add_argument("--storage-db", default="osap_storage")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    conn = pymysql.connect(
        host=args.host,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=True,
    )
    storage = pymysql.connect(
        host=args.host,
        user=args.user,
        password=args.password,
        database=args.storage_db,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(PROVIDERS))
            cur.execute(
                "SELECT COUNT(*) FROM index_representations "
                f"WHERE provider IN ({placeholders}) AND source_rep_id = '' "
                "AND download_url IS NOT NULL AND download_url <> ''",
                PROVIDERS,
            )
            pending = int(cur.fetchone()[0])
            print(f"representaciones pendientes: {pending}")
            if args.dry_run:
                return 0
            # IMSLP's API exposes a stable MediaWiki page id; use it when the
            # storage copy has the same permlink.
            cur.execute(
                "UPDATE index_representations r "
                f"JOIN {args.storage_db}.works w "
                "ON w.works_source_url = r.download_url AND w.works_origin = 'IMSLP' "
                "SET r.source_rep_id = w.works_origin_id "
                "WHERE r.provider = 'imslp' "
                "AND (r.source_rep_id = '' OR r.source_rep_id LIKE 'imslp:%')"
            )
            print(f"IMSLP con pageid: {cur.rowcount}")
            cur.execute(
                "UPDATE index_representations "
                f"SET source_rep_id = CONCAT(provider, ':', SHA1(download_url)) "
                f"WHERE provider IN ({placeholders}) AND source_rep_id = '' "
                "AND download_url IS NOT NULL AND download_url <> ''",
                PROVIDERS,
            )
            print(f"representaciones actualizadas: {cur.rowcount}")
    finally:
        storage.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
