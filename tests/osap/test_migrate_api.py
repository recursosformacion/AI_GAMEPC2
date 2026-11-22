"""Tests del splitter SQL del runner de migraciones de osap-api."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script.migrate_api import split_statements  # noqa: E402


def test_split_ignores_semicolon_in_string() -> None:
    sql = "CREATE TABLE t (c varchar(9) COMMENT 'a;b');\nINSERT INTO t VALUES ('x;y');\n"
    stmts = split_statements(sql)
    assert len(stmts) == 2
    assert "a;b" in stmts[0]
    assert "x;y" in stmts[1]


def test_split_simple_statements() -> None:
    assert split_statements("SET A=1; SET B=2;") == ["SET A=1", "SET B=2"]


def test_split_with_comments() -> None:
    sql = "-- comentario con ; dentro\nSET FOREIGN_KEY_CHECKS=0;\n"
    assert split_statements(sql) == ["-- comentario con ; dentro\nSET FOREIGN_KEY_CHECKS=0"]
