"""Tests de la limpieza de reps IMSLP duplicadas (normalización de título vs página)."""

from __future__ import annotations

from script.fix_imslp_rep_dupes import _norm, _page_core


def test_page_core_quita_sufijo_compositor() -> None:
    url = "https://imslp.org/wiki/10_Children%27s_Pieces,_RBV_13_(RSB)"
    assert _page_core(url) == _norm("10 Children's Pieces, RBV 13")


def test_norm_conserva_digitos() -> None:
    assert _norm("RBV 11") == "rbv11"
    assert _norm("RBV 11") != _norm("RBV 13")


def test_match_titulo_obra_con_pagina() -> None:
    url = "https://imslp.org/wiki/10_Children%27s_Pieces,_RBV_13_(RSB)"
    assert _norm("10 Children's Pieces, RBV 13") == _page_core(url)
    assert _norm("10 Children's Pieces, RBV 11") != _page_core(url)
