#!/usr/bin/env python
"""Generate old->new aliases from stable source URLs.

Use after importing an old index dump into a side database (for example
`osap_api_old`). It only creates aliases when `provider + download_url` matches
exactly one current work and title/person agree; it never uses title alone.

Usage:
    python script/backfill_index_url_aliases.py --old-db osap_api_old --database osap_api
    python script/backfill_index_url_aliases.py --old-db osap_api_old --dry-run
"""

from __future__ import annotations

import argparse

import pymysql


def _connect(args: argparse.Namespace, database: str) -> pymysql.Connection:
    return pymysql.connect(
        host=args.host,
        user=args.user,
        password=args.password,
        database=database,
        charset="utf8mb4",
        autocommit=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--user", default="osap2027")
    parser.add_argument("--password", default="2027osapdb")
    parser.add_argument("--old-db", required=True)
    parser.add_argument("--database", default="osap_api")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--resolve-ambiguous",
        action="store_true",
        help="Choose one canonical URL target when several current works share it",
    )
    args = parser.parse_args()
    old = _connect(args, args.old_db)
    live = _connect(args, args.database)
    try:
        with old.cursor() as old_cur, live.cursor() as cur:
            # A previous run may have left the side database without these indexes.
            for _database, conn, table, name, cols in (
                (args.old_db, old, "index_representations", "ix_old_provider_url",
                 "provider, download_url(191)"),
                (args.database, live, "index_representations", "ix_current_provider_url",
                 "provider, download_url(191)"),
            ):
                try:
                    with conn.cursor() as index_cur:
                        index_cur.execute(f"CREATE INDEX {name} ON {table} ({cols})")
                except pymysql.err.OperationalError as exc:
                    if exc.args[0] != 1061:
                        raise
            old_cur.execute("SELECT COUNT(*) FROM index_works")
            old_total = int(old_cur.fetchone()[0])
            cur.execute("DROP TEMPORARY TABLE IF EXISTS _pending_url_alias")
            cur.execute(
                "CREATE TEMPORARY TABLE _pending_url_alias (id BIGINT UNSIGNED PRIMARY KEY) "
                f"SELECT w.id FROM {args.old_db}.index_works w "
                f"LEFT JOIN {args.database}.index_id_aliases a ON a.old_id = w.id "
                "WHERE a.old_id IS NULL"
            )
            cur.execute("SELECT COUNT(*) FROM _pending_url_alias")
            pending = int(cur.fetchone()[0])
            print(f"obras antiguas: {old_total}; sin alias: {pending}")
            if args.dry_run or not pending:
                return 0
            cur.execute(
                f"INSERT IGNORE INTO {args.database}.index_id_aliases (old_id, new_id, method) "
                "SELECT o.work_id, MIN(n.work_id), 'source_url' "
                f"FROM _pending_url_alias p "
                f"JOIN {args.old_db}.index_works ow ON ow.id = p.id "
                f"JOIN {args.old_db}.index_representations o ON o.work_id = ow.id "
                "AND o.download_url IS NOT NULL AND o.download_url <> '' "
                f"JOIN {args.database}.index_representations n "
                "ON n.provider = o.provider AND n.download_url = o.download_url "
                f"JOIN {args.database}.index_works nw ON nw.id = n.work_id "
                "WHERE nw.title_key = ow.title_key "
                "AND nw.person_id <=> ow.person_id "
                "GROUP BY o.work_id HAVING COUNT(DISTINCT n.work_id) = 1"
            )
            print(f"aliases por URL insertados: {cur.rowcount}")
            if args.resolve_ambiguous:
                cur.execute("DROP TEMPORARY TABLE IF EXISTS _url_candidates")
                cur.execute(
                    "CREATE TEMPORARY TABLE _url_candidates AS "
                    "SELECT p.id AS old_id, nw.id AS new_id, "
                    "  CASE WHEN nw.title_key = ow.title_key "
                    "        AND nw.person_id <=> ow.person_id THEN 0 "
                    "       WHEN nw.person_id <=> ow.person_id "
                    "        AND nw.person_id IS NOT NULL THEN 1 "
                    "       WHEN nw.title_key = ow.title_key THEN 2 "
                    "       ELSE 3 END AS priority, "
                    "  nw.source_count "
                    "FROM _pending_url_alias p "
                    f"JOIN {args.old_db}.index_works ow ON ow.id = p.id "
                    f"JOIN {args.old_db}.index_representations o ON o.work_id = p.id "
                    "AND o.download_url IS NOT NULL AND o.download_url <> '' "
                    f"JOIN {args.database}.index_representations n "
                    "ON n.provider = o.provider AND n.download_url = o.download_url "
                    f"JOIN {args.database}.index_works nw ON nw.id = n.work_id"
                )
                cur.execute(
                    "CREATE INDEX ix_url_candidates_old ON _url_candidates "
                    "(old_id, priority, source_count, new_id)"
                )
                cur.execute(
                    "INSERT IGNORE INTO index_id_aliases (old_id, new_id, method) "
                    "SELECT old_id, new_id, 'source_url_best' FROM ("
                    "  SELECT old_id, new_id, ROW_NUMBER() OVER ("
                    "    PARTITION BY old_id ORDER BY priority, source_count DESC, new_id"
                    "  ) AS rn FROM _url_candidates"
                    ") ranked WHERE rn = 1"
                )
                print(f"aliases ambiguos resueltos: {cur.rowcount}")
                cur.execute("DROP TEMPORARY TABLE IF EXISTS _url_candidates")
            cur.execute("DROP TEMPORARY TABLE IF EXISTS _pending_url_alias")
    finally:
        old.close()
        live.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
