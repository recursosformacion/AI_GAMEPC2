#!/usr/bin/env python
"""Repara la asociación errónea Pieltain No.1/No.3 en el índice de osap-api.

Caso de referencia: la obra «Violin Concerto No.3 in B-flat major» (catálogo IDP 3)
absorbió la representación IMSLP de «Violin Concerto No.1 in F major» (source_rep_id
533293) porque ambas comparten `title_key="violin concerto"` y `person_id`, y el índice
tiene la clave única `(title_key, person_id)`. osap-storage ya las separa.

El script crea la obra No.1 (catálogo IDP 2) con su propia `title_key` desambiguada
(`violin concerto 1`) y mueve su representación; **no modifica** `public_id`, catálogo,
título ni `title_key` de la obra No.3, ni `index_id_aliases`/`legacy_index_map`, ni
osap-storage. La No.1 recibe su propio `public_id` determinista (no existía una obra
No.1 en el índice).

Uso (en osap-api):
    python script/repair_index_split_pieltain.py --api-db osap_api --storage-db osap_storage
    python script/repair_index_split_pieltain.py --api-db osap_api --storage-db osap_storage \
        --apply --backup-dir backups
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from index_works import (  # noqa: E402
    _catalogue_key,
    _disambiguated_tk,
    _public_id_for_record,
    title_key,
)

_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


def _ident(value: str, label: str) -> str:
    if not _IDENT.fullmatch(value):
        raise SystemExit(f"Identificador inválido para {label}: {value!r}")
    return value


def _q(value: str) -> str:
    return f"`{_ident(value, value)}`"


def _connect(args: argparse.Namespace) -> pymysql.Connection:
    password = os.environ.get("OSAP_DB_PASSWORD", args.db_password)
    return pymysql.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=password,
        database=args.api_db,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def _fetch_one(cur, sql: str, params: tuple) -> dict | None:
    cur.execute(sql, params)
    return cur.fetchone()


def _fetch_all(cur, sql: str, params: tuple) -> list[dict]:
    cur.execute(sql, params)
    return list(cur.fetchall())


def _table_exists(cur, database: str, table: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name=%s",
        (database, table),
    )
    return bool(cur.fetchone()["n"])


def _die(message: str) -> None:
    raise SystemExit(f"ABORT: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-db", default="osap_api")
    parser.add_argument("--storage-db", default="osap_storage")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios (por defecto dry-run)")
    parser.add_argument("--confirm-database", default="", help="Debe coincidir con --api-db para --apply")
    parser.add_argument(
        "--allow-production-write",
        action="store_true",
        help="Necesario para --apply sobre la BD de producción osap_api",
    )
    parser.add_argument("--backup-dir", default="backups")
    parser.add_argument("--no3-source", default="533295")
    parser.add_argument("--no1-source", default="533293")
    parser.add_argument("--no3-title", default="Violin Concerto No.3 in B-flat major")
    parser.add_argument("--no1-title", default="Violin Concerto No.1 in F major")
    parser.add_argument("--no3-catalogue", default="IDP 3")
    parser.add_argument("--no1-catalogue", default="IDP 2")
    args = parser.parse_args()

    if args.apply:
        if args.confirm_database != args.api_db:
            _die("--apply requiere --confirm-database con el nombre exacto de --api-db")
        if args.api_db in {"osap_api", "osap_storage"} and not args.allow_production_write:
            _die("escritura sobre una BD de producción bloqueada; añade --allow-production-write tras el backup")

    api = _q(args.api_db)
    storage = _q(args.storage_db)
    conn = _connect(args)
    try:
        with conn.cursor() as cur:
            no3_storage = _fetch_one(
                cur,
                f"SELECT id,works_title,works_catalogue,works_year,works_instrumentation"
                f" FROM {storage}.works WHERE works_origin='IMSLP' AND works_origin_id=%s LIMIT 2",
                (args.no3_source,),
            )
            no1_storage = _fetch_one(
                cur,
                f"SELECT id,works_title,works_catalogue,works_year,works_instrumentation"
                f" FROM {storage}.works WHERE works_origin='IMSLP' AND works_origin_id=%s LIMIT 2",
                (args.no1_source,),
            )
            if not no3_storage or not no1_storage:
                _die("no encuentro las obras No.1/No.3 en osap_storage por works_origin_id")
            if no3_storage["works_catalogue"] != args.no3_catalogue:
                _die(f"catálogo de la obra No.3 inesperado: {no3_storage['works_catalogue']!r}")
            if no1_storage["works_catalogue"] != args.no1_catalogue:
                _die(f"catálogo de la obra No.1 inesperado: {no1_storage['works_catalogue']!r}")

            no3 = _fetch_one(
                cur,
                f"SELECT w.id,w.public_id,w.title,w.title_key,w.composer_name,w.person_id,"
                f"w.catalogue,w.catalogue_key,w.year,w.instrumentation,w.source_count,"
                f"w.updated_at,w.genre_id"
                f" FROM {api}.index_works w"
                f" JOIN {api}.index_representations r ON r.work_id=w.id"
                f" WHERE r.provider='imslp' AND r.source_rep_id=%s"
                f" AND w.catalogue=%s AND w.title LIKE %s"
                f" GROUP BY w.id",
                (args.no3_source, args.no3_catalogue, args.no3_title + "%"),
            )
            if not no3:
                _die("no encuentro la obra No.3 en el índice vivo (catálogo IDP 3)")
            if no3["title"].strip() != args.no3_title:
                _die(f"título vivo No.3 inesperado: {no3['title']!r}")

            no3_reps = _fetch_all(
                cur,
                f"SELECT id,work_id,provider,source_rep_id,title_provider"
                f" FROM {api}.index_representations WHERE work_id=%s ORDER BY id",
                (no3["id"],),
            )
            no1_rep = next(
                (
                    row
                    for row in no3_reps
                    if row["provider"] == "imslp" and row["source_rep_id"] == args.no1_source
                ),
                None,
            )
            no3_rep = next(
                (
                    row
                    for row in no3_reps
                    if row["provider"] == "imslp" and row["source_rep_id"] == args.no3_source
                ),
                None,
            )
            if not no3_rep:
                _die("la obra No.3 no tiene su representación IMSLP 533295")
            if not no1_rep:
                no1_existing = _fetch_one(
                    cur,
                    f"SELECT w.id FROM {api}.index_works w"
                    f" JOIN {api}.index_representations r ON r.work_id=w.id"
                    f" WHERE r.provider='imslp' AND r.source_rep_id=%s"
                    f" AND w.catalogue=%s AND w.title LIKE %s LIMIT 2",
                    (args.no1_source, args.no1_catalogue, args.no1_title + "%"),
                )
                if no1_existing:
                    print("OK: la obra No.1 ya está separada; no hay nada que reparar.")
                    return 0
                _die("la representación No.1 no está bajo la obra No.3 y no existe una No.1 separada")

            new_key = _disambiguated_tk(title_key(args.no1_title), args.no1_title)
            # La obra No.1 no existía en el índice. En producción la No.3 pudo quedarse
            # con el public_id derivado de la fuente 533293 al absorber su representación;
            # para no tocar el public_id existente de la No.3, la No.1 usa un id nuevo y
            # estable basado en su obra de Storage.
            new_public_id = f"index-{int(no1_storage['id'])}"
            if _fetch_one(
                cur,
                f"SELECT id FROM {api}.index_works WHERE public_id=%s",
                (new_public_id,),
            ):
                new_public_id = _public_id_for_record(
                    {"provider": "imslp", "source_rep_id": args.no1_source}
                )
            conflict_key = _fetch_one(
                cur,
                f"SELECT id FROM {api}.index_works WHERE title_key=%s AND person_id <=> %s",
                (new_key, no3["person_id"]),
            )
            if conflict_key:
                _die(f"ya existe una obra con title_key={new_key!r} y la misma persona")
            conflict_pid = _fetch_one(
                cur,
                f"SELECT id FROM {api}.index_works WHERE public_id=%s",
                (new_public_id,),
            )
            if conflict_pid:
                _die(f"el public_id determinista ya existe: {new_public_id}")

            print("PLAN")
            print(f"  No.3 viva: id={no3['id']} public_id={no3['public_id']} "
                  f"catálogo={no3['catalogue']} title_key={no3['title_key']!r}")
            print(f"  Storage No.1: id={no1_storage['id']} {no1_storage['works_title']!r} "
                  f"catálogo={no1_storage['works_catalogue']}")
            print(f"  Mover rep IMSLP {args.no1_source} (id={no1_rep['id']}) "
                  f"de work {no3['id']} a la nueva obra No.1")
            print(f"  Nueva obra No.1: public_id={new_public_id} title_key={new_key!r} "
                  f"catálogo={no1_storage['works_catalogue']}")
            print(f"  Sin cambios: public_id/catálogo/title/title_key de No.{no3['id']}, "
                  "aliases/legacy map y osap_storage")

            if not args.apply:
                print("DRY-RUN: no se ha escrito nada. Usa --apply para aplicar.")
                return 0

            backup_dir = Path(args.backup_dir).expanduser()
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            backup_path = backup_dir / f"index_split_pieltain-{stamp}.json"
            backup = {
                "timestamp": datetime.now(UTC).isoformat(),
                "api_db": args.api_db,
                "storage_db": args.storage_db,
                "no3": no3,
                "no3_reps": no3_reps,
                "no3_voicings": _fetch_all(
                    cur,
                    f"SELECT work_id,kind,term FROM {api}.index_work_voicings WHERE work_id=%s",
                    (no3["id"],),
                ),
                "no1_rep": no1_rep,
                "si_aliases": _fetch_all(
                    cur,
                    f"SELECT * FROM {api}.index_id_aliases WHERE old_id=%s OR new_id=%s",
                    (no3["id"], no3["id"]),
                ),
                "legacy_map": (
                    _fetch_all(
                        cur,
                        f"SELECT * FROM {api}.legacy_index_map WHERE old_id=%s OR new_id=%s",
                        (no3["id"], no3["id"]),
                    )
                    if _table_exists(cur, args.api_db, "legacy_index_map")
                    else []
                ),
                "storage_no1": no1_storage,
                "storage_no3": no3_storage,
            }
            backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2, default=str),
                                   encoding="utf-8")
            print(f"Backup: {backup_path}")

            new_title = str(no1_storage["works_title"]).strip()
            cur.execute(
                f"INSERT INTO {api}.index_works "
                "(public_id,title,title_key,composer_name,person_id,catalogue,"
                "catalogue_key,year,instrumentation,source_count,updated_at,genre_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    new_public_id,
                    new_title[:1024],
                    new_key,
                    no3["composer_name"],
                    no3["person_id"],
                    str(no1_storage["works_catalogue"] or "").strip() or None,
                    _catalogue_key(no1_storage["works_catalogue"]),
                    no1_storage["works_year"],
                    (no1_storage["works_instrumentation"] or no3["instrumentation"] or "")[:255]
                    or None,
                    1,
                    no3["updated_at"],
                    no3["genre_id"],
                ),
            )
            new_id = int(cur.lastrowid)
            cur.execute(
                f"UPDATE {api}.index_representations SET work_id=%s WHERE id=%s AND work_id=%s",
                (new_id, no1_rep["id"], no3["id"]),
            )
            if cur.rowcount != 1:
                _die("no se pudo mover exactamente la representación No.1")
            cur.execute(
                f"INSERT IGNORE INTO {api}.index_work_voicings (work_id,kind,term) "
                f"SELECT %s,kind,term FROM {api}.index_work_voicings WHERE work_id=%s",
                (new_id, no3["id"]),
            )
            for work_id in (new_id, no3["id"]):
                cur.execute(
                    f"UPDATE {api}.index_works SET source_count="
                    f"(SELECT COUNT(*) FROM {api}.index_representations WHERE work_id=%s) "
                    "WHERE id=%s",
                    (work_id, work_id),
                )
            conn.commit()
            print(f"OK: nueva obra No.1 id={new_id} public_id={new_public_id} key={new_key!r}")
            print(f"OK: representación {no1_rep['id']} movida de {no3['id']} a {new_id}")
            return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
