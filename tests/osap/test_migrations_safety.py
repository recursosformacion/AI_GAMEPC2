"""Guardas de seguridad del baseline de migraciones de osap-api.

Comprueban que el baseline es no destructivo y que crea todas las tablas de forma
idempotente (`CREATE TABLE IF NOT EXISTS`). Es el test que faltaba para el baseline.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script.migrate_api import split_statements  # noqa: E402

BASELINE = ROOT / "migrations" / "001_baseline_schema.sql"


def test_baseline_is_non_destructive() -> None:
    text = BASELINE.read_text(encoding="utf-8").lower()
    assert "drop table" not in text
    assert "truncate" not in text
    assert "delete from" not in text


def test_baseline_creates_tables_idempotently() -> None:
    text = BASELINE.read_text(encoding="utf-8")
    creates = [
        s for s in split_statements(text) if s.lstrip().upper().startswith("CREATE TABLE")
    ]
    assert len(creates) == 49
    assert all("CREATE TABLE IF NOT EXISTS" in s.upper() for s in creates)
