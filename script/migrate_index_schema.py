#!/usr/bin/env python
"""Aplica las migraciones **de esquema** del índice de osap-api (idempotente).

El arranque de la app ya NO migra (`_MysqlStore._init` solo crea tablas con
`CREATE TABLE IF NOT EXISTS`); este script lanza `_migrate()` **una vez por despliegue**
para evitar DDL concurrente entre réplicas. Solo esquema: no toca filas.

Uso (desde osap-api):
    python script/migrate_index_schema.py
    python script/migrate_index_schema.py --database osap-api --host 127.0.0.1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.osap.infrastructure.state.op.mysql import _MysqlStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--user", default="osap2027")
    ap.add_argument("--password", default="2027osapdb")
    ap.add_argument("--database", default="osap-api")
    args = ap.parse_args()
    # __init__ crea las tablas si faltan; _migrate aplica los ALTER/index idempotentes.
    store = _MysqlStore(args.host, args.user, args.password, args.database)
    store._migrate()
    print("esquema del índice migrado (idempotente):", args.database)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
