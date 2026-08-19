#!/usr/bin/env python
"""Indexador local de obras — paso 1 del roadmap (fuente OMR).

Lee las obras del proveedor OMR (la BD de osap-storage) y puebla el índice local
(index_works + index_representations en la BD de osap-api), normalizando títulos
(title_key) y compositores (canonical + composer_id del Maestro) y deduplicando por
(title_key, composer_id).

La normalización es determinista: el índice GUARDA el resultado (no lo recalcula por
búsqueda). La sync es incremental; este script es la carga completa/inicial de OMR.

Uso (en osap-api, con PYTHONPATH=osap-api):
    python script/index_works.py --limit 1000 [--db-api osap-api] [--db-omr osap-storage]
"""

from __future__ import annotations

import argparse
import re
import sys

import pymysql

from src.osap.application.metadata_normalizer import MetadataNormalizer, title_key

_NORMALIZER = MetadataNormalizer()


def _catalogue_key(catalogue: str | None) -> str | None:
    if not catalogue:
        return None
    return re.sub(r"[^a-z0-9]", "", catalogue.lower()) or None


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--from-id", type=int, default=0)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-api", default="osap-api")
    parser.add_argument("--db-omr", default="osap-storage")
    args = parser.parse_args()

    api_db = {
        "host": args.db_host, "user": args.db_user, "password": args.db_password,
        "database": args.db_api, "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
    }
    omr_db = {
        "host": args.db_host, "user": args.db_user, "password": args.db_password,
        "database": args.db_omr, "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
    }

    omr = pymysql.connect(**omr_db)
    api = pymysql.connect(**api_db)
    try:
        with omr.cursor() as cur:
            cur.execute(
                "SELECT id, title, composer, composer_id, catalogue, year, "
                "instrumentation, relative_path, genre "
                "FROM works WHERE id > %s ORDER BY id LIMIT %s",
                (args.from_id, args.limit),
            )
            works = cur.fetchall()

        inserted = updated = 0
        with api.cursor() as cur:
            for w in works:
                title = str(w.get("title") or "")
                composer = w.get("composer")
                composer_id = w.get("composer_id")
                if not title.strip():
                    continue
                tk = title_key(title)
                cat_key = _catalogue_key(w.get("catalogue"))
                composer_name = _NORMALIZER.canonical_composer(composer) if composer else None
                year = w.get("year")
                year_int = int(year) if str(year or "").isdigit() else None
                cur.execute(
                    "INSERT INTO index_works (title, title_key, composer_name, composer_id, "
                    "catalogue, catalogue_key, year, instrumentation, source_count, updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,NOW()) "
                    "ON DUPLICATE KEY UPDATE title=VALUES(title), composer_name=VALUES(composer_name), "
                    "source_count=source_count, updated_at=NOW()",
                    (title[:1024], tk[:255], composer_name, composer_id,
                     (w.get("catalogue") or None), cat_key, year_int,
                     (w.get("instrumentation") or None)),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1
                if composer_id:
                    cur.execute(
                        "SELECT id FROM index_works WHERE title_key=%s AND composer_id=%s",
                        (tk[:255], composer_id),
                    )
                else:
                    cur.execute(
                        "SELECT id FROM index_works WHERE title_key=%s AND composer_id IS NULL",
                        (tk[:255],),
                    )
                row = cur.fetchone()
                if row is None:
                    continue
                work_id = row["id"]
                # Representación OMR (MusicXML). download_url pendiente del fix OMR.
                cur.execute(
                    "INSERT IGNORE INTO index_representations (work_id, provider, format, "
                    "download_url, title_provider, available, quality) "
                    "VALUES (%s,'omr','musicxml',NULL,%s,0,0)",
                    (work_id, title[:1024]),
                )
            api.commit()

        print("=== INDEX OMR ===")
        print(f"  obras leídas: {len(works)} | insertadas: {inserted} | actualizadas: {updated}")
        with api.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM index_works")
            print(f"  total index_works: {cur.fetchone()['n']}")
            cur.execute("SELECT COUNT(*) AS n FROM index_representations")
            print(f"  total index_representations: {cur.fetchone()['n']}")
    finally:
        omr.close()
        api.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
