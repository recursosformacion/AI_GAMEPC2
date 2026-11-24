"""Exporta el inventario de esquema de osap-api mediante consultas de solo lectura."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from src.osap.bootstrap.configuration import load_configuration


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta tablas, columnas, índices y claves foráneas de la BD API."
    )
    parser.add_argument(
        "--confirm-database",
        required=True,
        help="Debe coincidir exactamente con osap_api_db_name de la configuración activa.",
    )
    parser.add_argument(
        "--allow-production-read",
        action="store_true",
        help="Permite ejecutar SELECT en una BD marcada como producción.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Fichero Markdown de salida. Si se omite, imprime por stdout.",
    )
    return parser.parse_args()


def _md(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _safe_default(column_name: str, value: Any) -> str:
    if value is None:
        return "—"
    sensitive = ("password", "secret", "token", "api_key", "private_key")
    if any(term in column_name.lower() for term in sensitive):
        return "[REDACTED]"
    return _md(value)


def _render(database: str, tables: list[dict[str, Any]], columns: list[dict[str, Any]],
            indexes: list[dict[str, Any]], foreign_keys: list[dict[str, Any]]) -> str:
    lines = [
        "# Inventario de esquema de osap-api",
        "",
        "> Generado mediante consultas SQL de solo lectura. TABLE_ROWS es una estimación de InnoDB.",
        "",
        f"**Base de datos:** {database}",
        f"**Tablas:** {len(tables)}",
        "",
        "## Resumen",
        "",
        "| Tabla | Motor | Filas estimadas | Comentario |",
        "|---|---|---:|---|",
    ]
    for table in tables:
        lines.append(
            f"| {_md(table.get('TABLE_NAME'))} | {_md(table.get('ENGINE'))} | "
            f"{_md(table.get('TABLE_ROWS'))} | {_md(table.get('TABLE_COMMENT'))} |"
        )

    for table in tables:
        name = str(table["TABLE_NAME"])
        table_columns = [row for row in columns if row["TABLE_NAME"] == name]
        table_indexes = [row for row in indexes if row["TABLE_NAME"] == name]
        table_fks = [row for row in foreign_keys if row["TABLE_NAME"] == name]
        lines.extend(
            [
                "",
                f"## {name}",
                "",
                "| # | Columna | Tipo | Nulo | Default | Clave | Extra | Comentario |",
                "|---:|---|---|---|---|---|---|---|",
            ]
        )
        for row in table_columns:
            lines.append(
                f"| {row.get('ORDINAL_POSITION')} | {_md(row.get('COLUMN_NAME'))} | "
                f"{_md(row.get('COLUMN_TYPE'))} | {_md(row.get('IS_NULLABLE'))} | "
                f"{_safe_default(str(row.get('COLUMN_NAME') or ''), row.get('COLUMN_DEFAULT'))} | {_md(row.get('COLUMN_KEY'))} | "
                f"{_md(row.get('EXTRA'))} | {_md(row.get('COLUMN_COMMENT'))} |"
            )
        if table_indexes:
            lines.extend(["", "### Índices", "", "| Índice | Único | Posición | Columna |", "|---|---:|---:|---|"])
            for row in table_indexes:
                lines.append(
                    f"| {_md(row.get('INDEX_NAME'))} | "
                    f"{'no' if row.get('NON_UNIQUE') else 'sí'} | "
                    f"{_md(row.get('SEQ_IN_INDEX'))} | {_md(row.get('COLUMN_NAME'))} |"
                )
        if table_fks:
            lines.extend(["", "### Claves foráneas", "", "| Restricción | Columna | Tabla referenciada | Columna referenciada |", "|---|---|---|---|"])
            for row in table_fks:
                lines.append(
                    f"| {_md(row.get('CONSTRAINT_NAME'))} | {_md(row.get('COLUMN_NAME'))} | "
                    f"{_md(row.get('REFERENCED_TABLE_NAME'))} | "
                    f"{_md(row.get('REFERENCED_COLUMN_NAME'))} |"
                )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    config = load_configuration()
    database = str(config.osap_api_db_name or "")
    if not database:
        print("ERROR: falta osap_api_db_name.", file=sys.stderr)
        return 2
    if args.confirm_database != database:
        print("ERROR: --confirm-database no coincide con la BD configurada.", file=sys.stderr)
        return 2
    deployment = str(config.deployment or "").lower()
    if deployment in {"prod", "production"} and not args.allow_production_read:
        print(
            "ERROR: entorno productivo; requiere --allow-production-read.",
            file=sys.stderr,
        )
        return 2

    required = {
        "host": config.osap_api_db_host,
        "user": config.osap_api_db_user,
        "password": config.osap_api_db_password,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        print("ERROR: faltan parámetros de conexión: " + ", ".join(missing), file=sys.stderr)
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
                "SELECT TABLE_NAME, ENGINE, TABLE_ROWS, TABLE_COMMENT "
                "FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s "
                "AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
                (database,),
            )
            tables = list(cur.fetchall())
            cur.execute(
                "SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, "
                "IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY, EXTRA, COLUMN_COMMENT "
                "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s "
                "ORDER BY TABLE_NAME, ORDINAL_POSITION",
                (database,),
            )
            columns = list(cur.fetchall())
            cur.execute(
                "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME "
                "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s "
                "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
                (database,),
            )
            indexes = list(cur.fetchall())
            cur.execute(
                "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, "
                "REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s "
                "AND REFERENCED_TABLE_NAME IS NOT NULL "
                "ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION",
                (database,),
            )
            foreign_keys = list(cur.fetchall())
        markdown = _render(database, tables, columns, indexes, foreign_keys)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(markdown, encoding="utf-8")
            print(f"Inventario escrito en {args.output} ({len(tables)} tablas).")
        else:
            print(markdown)
        return 0
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
