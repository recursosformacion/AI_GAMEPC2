#!/usr/bin/env python
"""Aplica las migraciones SQL de osap-api (idempotente).

Lee `migrations/*.sql`, aplica las pendientes y las registra en `schema_migrations`.
El splitter de sentencias respeta `;` dentro de cadenas/comentarios (los esquemas
volcados incluyen `COMMENT '...;...'`).

Uso:
    python script/migrate_api.py --db-user osap2027 --db-password *** --db-name osap_api

La baseline 001 es solo de esquema (49 CREATE TABLE IF NOT EXISTS): no importa datos
ni altera columnas de tablas existentes. En una BD ya poblada no corrige drift; antes
de registrarla como aplicada hay que comparar el esquema real con el de desarrollo.
No ejecutar sobre una BD existente suponiendo que IF NOT EXISTS la actualiza.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymysql  # noqa: E402
from pymysql.cursors import DictCursor  # noqa: E402

MIGRATIONS_DIR = ROOT / "migrations"


def split_statements(text: str) -> list[str]:
    """Divide SQL en sentencias respetando cadenas y comentarios."""
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(text)
    mode: str | None = None  # None | "'" | '"' | "`" | "line" | "block"
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if mode is None:
            if ch == "-" and nxt == "-":
                mode = "line"
                buf.extend((ch, nxt))
                i += 2
                continue
            if ch == "/" and nxt == "*":
                mode = "block"
                buf.extend((ch, nxt))
                i += 2
                continue
            if ch in ("'", '"', "`"):
                mode = ch
                buf.append(ch)
                i += 1
                continue
            if ch == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    statements.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue
        if mode == "line":
            buf.append(ch)
            if ch == "\n":
                mode = None
            i += 1
            continue
        if mode == "block":
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                mode = None
                continue
            i += 1
            continue
        # dentro de cadena/identificador
        buf.append(ch)
        if ch == "\\" and i + 1 < n:
            buf.append(nxt)
            i += 2
            continue
        if ch == mode:
            if nxt == mode:
                buf.append(nxt)
                i += 2
                continue
            mode = None
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-host", default=os.environ.get("OSAP_DB_HOST", "127.0.0.1"))
    ap.add_argument("--db-port", type=int, default=int(os.environ.get("OSAP_DB_PORT", "3306")))
    ap.add_argument("--db-user", default=os.environ.get("OSAP_DB_USER", ""))
    ap.add_argument("--db-password", default=os.environ.get("OSAP_DB_PASSWORD", ""))
    ap.add_argument("--db-name", default=os.environ.get("OSAP_DB_NAME", "osap_api"))
    args = ap.parse_args()
    if not args.db_user:
        ap.error("falta usuario de BD (OSAP_DB_USER o --db-user)")

    conn = pymysql.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,"
                "name VARCHAR(255) NOT NULL,"
                "applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),"
                "PRIMARY KEY (id), UNIQUE KEY uq_schema_migrations_name (name)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
            )
            conn.commit()
            cur.execute("SELECT name FROM schema_migrations")
            applied = {str(row["name"]) for row in cur.fetchall()}

        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in applied:
                continue
            for stmt in split_statements(sql_file.read_text(encoding="utf-8")):
                with conn.cursor() as cur:
                    cur.execute(stmt)
            with conn.cursor() as cur:
                cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (sql_file.name,))
            conn.commit()
            print(f"applied {sql_file.name}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
