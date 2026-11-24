"""Auditoría SQL de solo lectura de las representaciones asociadas a una Work.

Por defecto inspecciona una sola public_id. Nunca corrige datos ni ejecuta DDL.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.bootstrap.configuration import load_configuration


DEFAULT_PUBLIC_ID = "index-376284cace625701f1ef"


def _number_conflict(work_title: str, representation_title: str) -> tuple[str | None, str | None]:
    work_number = MetadataNormalizer.normalize(work_title, None).normalized_number
    representation_number = MetadataNormalizer.normalize(
        representation_title, None
    ).normalized_number
    if work_number and representation_number and work_number != representation_number:
        return work_number, representation_number
    return None, None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspecciona en solo lectura las representaciones de una Work del índice."
    )
    parser.add_argument("--public-id", default=DEFAULT_PUBLIC_ID)
    parser.add_argument(
        "--confirm-database",
        required=True,
        help="Debe coincidir exactamente con osap_api_db_name del osap.toml activo.",
    )
    parser.add_argument(
        "--allow-production-read",
        action="store_true",
        help="Permite una consulta SQL de solo lectura si OSAP_DEPLOYMENT es prod.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = load_configuration()

    database = str(config.osap_api_db_name or "")
    if not database:
        print("ERROR: falta osap_api_db_name en la configuración activa.", file=sys.stderr)
        return 2
    if args.confirm_database != database:
        print(
            f"ERROR: la BD activa no coincide con --confirm-database (BD configurada: {database}).",
            file=sys.stderr,
        )
        return 2

    deployment = str(config.deployment or "").lower()
    if deployment in {"prod", "production"} and not args.allow_production_read:
        print(
            "ERROR: entorno productivo. Repite solo si autorizas expresamente la lectura "
            "con --allow-production-read.",
            file=sys.stderr,
        )
        return 2

    required = {
        "host": config.osap_api_db_host,
        "user": config.osap_api_db_user,
        "password": config.osap_api_db_password,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print("ERROR: faltan valores de conexión: " + ", ".join(missing), file=sys.stderr)
        return 2

    conn = pymysql.connect(
        host=str(config.osap_api_db_host),
        user=str(config.osap_api_db_user),
        password=str(config.osap_api_db_password),
        database=database,
        port=int(config.osap_api_db_port),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("START TRANSACTION READ ONLY")
            cur.execute(
                "SELECT id, public_id, title, composer_name, catalogue "
                "FROM index_works WHERE public_id = %s LIMIT 1",
                (args.public_id,),
            )
            work = cur.fetchone()
            if not work:
                print(f"No existe la Work {args.public_id!r} en index_works.")
                return 1

            cur.execute(
                "SELECT provider, format, download_url, available, resource_id, source_rep_id, "
                "title_provider, xml_title "
                "FROM index_representations WHERE work_id = %s "
                "ORDER BY provider, format",
                (work["id"],),
            )
            representations = cur.fetchall()

        work_title = str(work.get("title") or "")
        print("READ-ONLY transaction; no se realizan escrituras.")
        print(
            f"WORK id={work.get('id')} public_id={work.get('public_id')} "
            f"composer={work.get('composer_name')} catalogue={work.get('catalogue')}"
        )
        print(f"TITLE {work_title}")
        conflicts = 0
        for row in representations:
            title = str(row.get("title_provider") or row.get("xml_title") or "")
            work_number, rep_number = _number_conflict(work_title, title)
            status = "CONFLICT" if work_number else "OK"
            if work_number:
                conflicts += 1
            print(
                f"{status} provider={row.get('provider')} format={row.get('format')} "
                f"source_rep_id={row.get('source_rep_id')} resource_id={row.get('resource_id')} "
                f"available={row.get('available')} title={title!r}"
            )
            if work_number:
                print(
                    f"  NUMBER_MISMATCH work_number={work_number} "
                    f"representation_number={rep_number}"
                )
        print(
            f"SUMMARY representations={len(representations)} "
            f"number_conflicts={conflicts}"
        )
        return 0
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
