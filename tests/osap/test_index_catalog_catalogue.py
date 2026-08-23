"""Tests de búsqueda difusa de catálogos en el índice local (KV/BWV/Op./D.)."""

from src.osap.infrastructure.catalogs.index.index_catalog_provider import (
    _catalogue_normalized,
    _catalogue_variants,
)


def test_catalogue_normalized() -> None:
    cases = {
        "K. 618": "k618",
        "KV 618": "k618",
        "k618": "k618",
        "Koch. Ver. No. 618": "k618",
        "Kochel Verzeichnis 618": "k618",
        "K\u00f6chel 618": "k618",
        "BWV 232": "bwv232",
        "BWV.232": "bwv232",
        "Op. 27 No. 2": "op27",
        "D. 547": "d547",
        "Hob. XVI:50": "hobxvi50",
    }
    for raw, expected in cases.items():
        assert _catalogue_normalized(raw) == expected, f"{raw} -> {expected}"


def test_catalogue_variants() -> None:
    variants = set(_catalogue_variants("D 547"))
    assert "D.547" in variants
    assert "D547" in variants
    assert "D 547" in variants

    variants_kv = set(_catalogue_variants("KV 618"))
    assert "KV618" in variants_kv
    assert "KV.618" in variants_kv
    assert "KV 618" in variants_kv

    assert _catalogue_variants("ave verum corpus") == []


def test_catalogue_variants_in_compound_query() -> None:
    variants = set(_catalogue_variants("BWV 232 h-moll"))
    assert "BWV 232" in variants
    assert "BWV232" in variants
