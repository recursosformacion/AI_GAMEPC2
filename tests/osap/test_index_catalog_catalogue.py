"""Tests de búsqueda difusa de catálogos en el índice local (KV/BWV/Op./D.)."""

from src.osap.domain.search_request import SearchRequest
from src.osap.infrastructure.catalogs.index.index_catalog_provider import (
    _build_sql,
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


def test_build_sql_texto_libre_usa_fulltext_con_token_unico() -> None:
    """Un único token >=3 chars sin catálogo usa MATCH (índice FULLTEXT)."""
    sql, args = _build_sql(SearchRequest(query="moz"), 400, use_fulltext=True)
    assert sql is not None
    assert "MATCH(i.title, i.composer_name) AGAINST" in sql
    assert args[0] == "moz*"


def test_build_sql_texto_libre_sin_fulltext_cae_a_like() -> None:
    """Sin el índice FULLTEXT, la búsqueda libre vuelve a LIKE (fallback seguro)."""
    sql, args = _build_sql(SearchRequest(query="moz"), 400, use_fulltext=False)
    assert sql is not None
    assert "MATCH" not in sql
    assert "title LIKE" in sql
    assert "%moz%" in args


def test_build_sql_texto_libre_multi_palabra_usa_like() -> None:
    """Varias palabras no usan MATCH (FULLTEXT no matchea subcadenas bien)."""
    sql, args = _build_sql(SearchRequest(query="ave verum"), 400, use_fulltext=True)
    assert sql is not None
    assert "MATCH" not in sql
    assert "%ave verum%" in args


def test_build_sql_token_corto_usa_like() -> None:
    """Tokens <3 chars no usan MATCH (limitación del token mínimo de FULLTEXT)."""
    sql, args = _build_sql(SearchRequest(query="mo"), 400, use_fulltext=True)
    assert sql is not None
    assert "MATCH" not in sql
    assert "%mo%" in args


def test_build_sql_catalogo_ignora_fulltext() -> None:
    """Una query que ES un catálogo (K 618) no usa MATCH."""
    sql, args = _build_sql(SearchRequest(query="K 618"), 400, use_fulltext=True)
    assert sql is not None
    assert "MATCH" not in sql
    assert "catalogue_key LIKE" in sql
