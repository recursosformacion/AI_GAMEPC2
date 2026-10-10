"""Tests del reconciliador de reps IMSLP (identidad por número/Op.)."""

from __future__ import annotations

from script.reconcile_imslp_reps import _core, _numbers, _page_title


def test_page_title_decodifica() -> None:
    url = "https://imslp.org/wiki/10_Fantasistykker,_Op.36_(Backer-Gr%C3%B8ndahl,_Agathe)"
    assert _page_title(url) == "10 Fantasistykker, Op.36 (Backer-Grøndahl, Agathe)"


def test_numbers_detectan_op_distinto() -> None:
    a = _numbers("10 Fantasistykker, Op.36 (Backer)")
    b = _numbers("10 Fantasistykker, Op.39")
    assert a != b
    assert "36" in a and "39" in b


def test_core_quita_sufijo_compositor() -> None:
    assert _core("10 Fantasistykker, Op.36 (Backer-Grøndahl, Agathe)") == _core("10 Fantasistykker, Op.36")


def test_mismos_numeros_no_conflictan() -> None:
    assert _numbers("10 Gesänge, Op.97") == _numbers("10 Gesänge für Männerchor, Op.97")
