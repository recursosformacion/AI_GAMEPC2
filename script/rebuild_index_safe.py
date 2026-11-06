#!/usr/bin/env python
"""Rebuild the index in a shadow database and merge it without changing live IDs.

Usage:
    python script/rebuild_index_safe.py --providers omr,cpdl --limit 0
    python script/rebuild_index_safe.py --providers omr --limit 5 --db-build osap_index_build_test

The shadow database is populated by `index_works.py`. Only natural identity
(title_key + person_id + catalogue) is used to merge; live `index_works.id`
values are never replaced. Works absent from the shadow build are left intact
for a later explicit pruning step.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
INDEX_TABLES = ("index_works", "index_representations", "index_work_voicings")


def connect(host: str, user: str, password: str, database: str | None = None) -> pymysql.Connection:
    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        autocommit=True,
    )


def prepare_build(conn: pymysql.Connection, build_db: str, live_db: str) -> None:
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{build_db}` CHARACTER SET utf8mb4 "
                    "COLLATE utf8mb4_unicode_ci")
        for table in INDEX_TABLES:
            cur.execute(f"DROP TABLE IF EXISTS `{build_db}`.`{table}`")
            cur.execute(f"CREATE TABLE `{build_db}`.`{table}` LIKE `{live_db}`.`{table}`")


def merge(conn: pymysql.Connection, build_db: str, live_db: str) -> tuple[int, int]:
    """Merge by source identity first, then title only as a fallback."""
    with conn.cursor() as cur:
        cur.execute("DROP TEMPORARY TABLE IF EXISTS _osap_index_map")
        cur.execute(
            "CREATE TEMPORARY TABLE _osap_index_map "
            "(build_id BIGINT UNSIGNED PRIMARY KEY, live_id BIGINT UNSIGNED NOT NULL)"
        )
        # Stable provider/source identity. This is the primary reconstruction key.
        cur.execute(
            f"""
            INSERT INTO _osap_index_map (build_id, live_id)
            SELECT br.work_id, MIN(lr.work_id)
            FROM `{build_db}`.index_representations br
            JOIN `{live_db}`.index_representations lr
              ON lr.provider = br.provider
             AND lr.source_rep_id = br.source_rep_id
             AND lr.source_rep_id <> ''
            GROUP BY br.work_id
            HAVING COUNT(DISTINCT lr.work_id) = 1
            """
        )
        cur.execute(
            f"""
            UPDATE `{live_db}`.index_works l
            JOIN _osap_index_map m ON m.live_id = l.id
            JOIN `{build_db}`.index_works b ON b.id = m.build_id
            SET l.title = b.title,
                l.composer_name = b.composer_name,
                l.catalogue = b.catalogue,
                l.catalogue_key = b.catalogue_key,
                l.year = b.year,
                l.instrumentation = b.instrumentation,
                l.source_count = b.source_count,
                l.updated_at = b.updated_at,
                l.genre_id = b.genre_id
            """
        )
        updated = cur.rowcount
        inserted = 0

        # No title matching: a title is search metadata, never identity.
        # Build works without a source match are genuinely new (or have no
        # stable source ID); insert them and key the mapping by their source
        # representation afterward.
        cur.execute(
            f"""
            SELECT b.id, b.title, b.title_key, b.composer_name, b.person_id,
                   b.catalogue, b.catalogue_key, b.year, b.instrumentation,
                   b.source_count, b.updated_at, b.genre_id
            FROM `{build_db}`.index_works b
            LEFT JOIN _osap_index_map m ON m.build_id = b.id
            WHERE m.build_id IS NULL
            """
        )
        for row in cur.fetchall():
            cur.execute(
                f"""
                INSERT INTO `{live_db}`.index_works
                    (title, title_key, composer_name, person_id, catalogue,
                     catalogue_key, year, instrumentation, source_count, updated_at, genre_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row["title"], row["title_key"], row["composer_name"], row["person_id"],
                    row["catalogue"], row["catalogue_key"], row["year"],
                    row["instrumentation"], row["source_count"], row["updated_at"],
                    row["genre_id"],
                ),
            )
            cur.execute(
                "INSERT INTO _osap_index_map (build_id, live_id) VALUES (%s,%s)",
                (row["id"], cur.lastrowid),
            )
            inserted += 1

        cur.execute(
            f"""
            DELETE r FROM `{live_db}`.index_representations r
            JOIN _osap_index_map m ON m.live_id = r.work_id
            """
        )
        cur.execute(
            f"""
            INSERT INTO `{live_db}`.index_representations
                (work_id, provider, format, download_url, title_provider,
                 available, quality, content_hash, xml_title, xml_composer,
                 source_rep_id, resource_id)
            SELECT m.live_id, b.provider, b.format, b.download_url, b.title_provider,
                   b.available, b.quality, b.content_hash, b.xml_title, b.xml_composer,
                   b.source_rep_id, b.resource_id
            FROM `{build_db}`.index_representations b
            JOIN _osap_index_map m ON m.build_id = b.work_id
            """
        )

        cur.execute(
            f"""
            DELETE v FROM `{live_db}`.index_work_voicings v
            JOIN _osap_index_map m ON m.live_id = v.work_id
            """
        )
        cur.execute(
            f"""
            INSERT INTO `{live_db}`.index_work_voicings (work_id, kind, term)
            SELECT m.live_id, b.kind, b.term
            FROM `{build_db}`.index_work_voicings b
            JOIN _osap_index_map m ON m.build_id = b.work_id
            """
        )
        cur.execute("DROP TEMPORARY TABLE _osap_index_map")
    return updated, inserted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", default="omr,cpdl")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--user", default="osap2027")
    parser.add_argument("--password", default=os.environ.get("OSAP_INDEX_DB_PASSWORD", ""))
    parser.add_argument("--db-api", default="osap_api")
    parser.add_argument("--db-omr", default="osap_storage")
    parser.add_argument("--db-build", default=None)
    parser.add_argument("--omr-base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    build_db = args.db_build or f"osap_index_build_{time.strftime('%Y%m%d_%H%M%S')}"
    admin = connect(args.host, args.user, args.password, args.db_api)
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT GET_LOCK('osap_index_jobs', 0) AS got")
            if not cur.fetchone()[0]:
                print("otro job de índice está en ejecución; salgo")
                return 75
        prepare_build(admin, build_db, args.db_api)
        env = {**os.environ, "PYTHONPATH": str(ROOT), "OSAP_INDEX_DB_PASSWORD": args.password}
        cmd = [
            sys.executable, str(ROOT / "script" / "index_works.py"),
            "--providers", args.providers,
            "--limit", str(args.limit),
            "--db-host", args.host,
            "--db-user", args.user,
            "--db-api", build_db,
            "--db-omr", args.db_omr,
            "--omr-base-url", args.omr_base_url,
            "--from-id", "0",
        ]
        print("construyendo índice shadow:", build_db, flush=True)
        rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
        if rc != 0:
            print("falló la construcción del índice shadow; no se fusiona")
            return rc
        updated, inserted = merge(admin, build_db, args.db_api)
        print(f"merge: actualizadas={updated} insertadas={inserted}; live IDs preservados")
        print("shadow:", build_db)
        return 0
    finally:
        admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
