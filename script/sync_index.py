#!/usr/bin/env python
"""Sincronización incremental del índice local con las fuentes externas.

Orquesta `index_works.py` con estado persistido en `sync_state` (tabla de osap-api),
para que cada pasada reanude donde terminó la anterior:

  * imslp  -> Worklist API paginada por `start` (se guarda el último `start` procesado).
  * omr    -> obras de osap-storage con id > último procesado (nuevas del corpus).
  * mutopia-> catálogo completo (pequeño), siempre desde 0.
  * musicbrainz -> dump local (manual, requiere `--mb-dump` y suele ser una carga completa).

Cada proveedor es idempotente: reindexar una obra ya presente actualiza sus metadatos en
vez de duplicarla (dedupe por `title_key`+`composer_id`).

Uso (en osap-api, con PYTHONPATH=osap-api):
    python script/sync_index.py --providers imslp,omr,mutopia \
        [--db-api osap_api] [--db-omr osap_storage] [--db-user U] [--db-password P] \
        [--omr-base-url https://storage.openmusicrepository.com] [--mb-dump <dir>]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Claves de estado persistentes en sync_state.
_KEYS = {
    "imslp": "index.imslp.start",
    "omr": "index.omr.last_work_id",
    "mutopia": "index.mutopia.start_at",
}


def _db_connect(args: argparse.Namespace) -> pymysql.Connection:
    return pymysql.connect(
        host=args.db_host, user=args.db_user, password=args.db_password,
        database=args.db_api, charset="utf8mb4", cursorclass=DictCursor,
        autocommit=True,
    )


def _get_state(conn: pymysql.Connection, key: str) -> str | None:
    with conn.cursor(DictCursor) as cur:
        cur.execute("SELECT value FROM sync_state WHERE `key` = %s", (key,))
        row = cur.fetchone()
        return str(row["value"]) if row else None


def _set_state(conn: pymysql.Connection, key: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sync_state (`key`, value, updated_at) VALUES (%s, %s, NOW()) "
            "ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)",
            (key, value),
        )


def _run_indexer(args: argparse.Namespace, extra: list[str]) -> int:
    cmd = [sys.executable, str(ROOT / "script" / "index_works.py")]
    cmd += ["--db-api", args.db_api, "--db-omr", args.db_omr,
            "--db-user", args.db_user, "--db-password", args.db_password]
    if args.db_host != "127.0.0.1":
        cmd += ["--db-host", args.db_host]
    cmd += extra
    print(f"  -> {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd)


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", default="imslp,omr,mutopia")
    parser.add_argument("--imslp-verify-ssl", action="store_true")
    parser.add_argument("--mb-dump", default=None)
    parser.add_argument("--mb-types", choices=("art", "all"), default="art")
    parser.add_argument("--omr-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-api", default="osap-api")
    parser.add_argument("--db-omr", default="osap-storage")
    args = parser.parse_args()

    conn = _db_connect(args)
    try:
        for provider in [p.strip() for p in args.providers.split(",") if p.strip()]:
            print(f"=== SYNC {provider} ===", flush=True)
            if provider == "imslp":
                # La Worklist API de IMSLP no expone "cambios recientes" de forma fiable:
                # relanzar desde start=0 (idempotente; el dedupe actualiza en vez de duplicar).
                # sync_state guarda el último start solo para reanudar pasadas interrumpidas.
                start = int(_get_state(conn, _KEYS["imslp"]) or 0)
                print(f"  reanudando desde start={start} (0 = pasada completa)", flush=True)
                rc = _run_indexer(args, [
                    "--providers", "imslp", "--limit", "0",
                    "--imslp-start", str(start),
                ] + (["--imslp-verify-ssl"] if args.imslp_verify_ssl else []))
                if rc != 0:
                    print("  error indexando imslp", flush=True)
                    continue
                # Tras éxito, resetear el marcador: la siguiente pasada vuelve a ser completa.
                _set_state(conn, _KEYS["imslp"], "0")
            elif provider == "omr":
                state_key = _KEYS["omr"]
                from_id = int(_get_state(conn, state_key) or 0)
                print(f"  reanudando desde work_id={from_id}", flush=True)
                rc = _run_indexer(args, [
                    "--providers", "omr", "--limit", "0", "--from-id", str(from_id),
                    "--omr-base-url", args.omr_base_url,
                ])
                if rc != 0:
                    print("  error indexando omr", flush=True)
                    continue
                # estado: máximo work_id de osap-storage (nuevas obras en la siguiente pasada)
                with conn.cursor(DictCursor) as cur:
                    cur.execute("SELECT MAX(id) AS mx FROM works")
                    row = cur.fetchone()
                if row and row["mx"] is not None:
                    _set_state(conn, state_key, str(int(row["mx"])))
            elif provider == "mutopia":
                _run_indexer(args, ["--providers", "mutopia", "--limit", "0"])
            elif provider == "musicbrainz":
                if not args.mb_dump:
                    print("  error: --mb-dump es obligatorio para musicbrainz", flush=True)
                    continue
                _run_indexer(args, [
                    "--providers", "musicbrainz", "--limit", "0",
                    "--mb-dump", args.mb_dump, "--mb-types", args.mb_types,
                ])
            else:
                print(f"  proveedor desconocido: {provider}", flush=True)
        print("=== SYNC COMPLETADO ===")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
