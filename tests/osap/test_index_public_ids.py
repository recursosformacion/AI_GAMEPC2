"""Test del dedupe por `public_id` en la inserción por lote del índice."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script.index_works import _dedupe_by_public_id  # noqa: E402


def test_dedupe_by_public_id_drops_repeats() -> None:
    rows = [
        ("index-aaaa", "Title A", "tk-a"),
        ("index-bbbb", "Title B", "tk-b"),
        ("index-aaaa", "Other", "tk-c"),
        ("index-cccc", "Title C", "tk-d"),
    ]
    out, skipped = _dedupe_by_public_id(rows)
    assert [row[0] for row in out] == ["index-aaaa", "index-bbbb", "index-cccc"]
    assert skipped == 1


def test_dedupe_by_public_id_keeps_unique() -> None:
    rows = [("index-aaaa",), ("index-bbbb",)]
    out, skipped = _dedupe_by_public_id(rows)
    assert out == rows
    assert skipped == 0
