"""Tests del splitter SQL del runner de migraciones de osap-api."""

from __future__ import annotations

import re
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



def test_api_baseline_is_schema_only_and_additive() -> None:
    baseline = (ROOT / "migrations" / "001_baseline_schema.sql").read_text(encoding="utf-8")

    assert len(re.findall(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS", baseline, re.I)) == 49
    parsed = split_statements(baseline)
    assert sum(
        bool(re.match(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS", statement, re.I))
        for statement in parsed
    ) == 49
    assert not re.search(
        r"\b(?:ALTER\s+TABLE|DROP\s+(?:TABLE|COLUMN|DATABASE)|"
        r"TRUNCATE\s+TABLE|INSERT\s+INTO|UPDATE\s+[^;]+\s+SET|DELETE\s+FROM)\b",
        baseline,
        re.I,
    )
    assert "FOREIGN_KEY_CHECKS=0" in baseline
    assert "FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS" in baseline
