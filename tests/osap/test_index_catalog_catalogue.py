"""Tests de búsqueda difusa de catálogos en el índice local (KV/BWV/Op./D.)."""

from src.osap.domain.output_format import OutputFormat
from src.osap.domain.search_request import SearchRequest
from src.osap.infrastructure.catalogs.index.index_catalog_provider import (
    _FORMAT_BY_VALUE,
    _build_sql,
    _catalogue_normalized,
    _catalogue_variants,
    _row_to_candidate,
)


def _row(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 388634,
        "title": "Ave verum corpus",
        "composer_name": "Wolfgang Amadeus Mozart",
        "catalogue": "KV 618",
        "year": 1791,
        "provider": "cpdl",
        "format": "pdf",
        "download_url": "https://www.cpdl.org/wiki/x.pdf",
        "available": 0,
        "quality": 0,
        "source_rep_id": "",
        "resource_id": 0,
    }
    row.update(over)
    return row


def test_formatos_cpdl_no_se_disfrazan() -> None:
    """MUS/SIB/MSCZ/audio se aceptan como formatos propios (no como MusicXML/PDF)."""
    assert _FORMAT_BY_VALUE["mus"] == OutputFormat.MUS
    assert _FORMAT_BY_VALUE["sib"] == OutputFormat.SIB
    assert _FORMAT_BY_VALUE["mscz"] == OutputFormat.MSCZ
    assert _FORMAT_BY_VALUE["capx"] == OutputFormat.CAPX
    assert _FORMAT_BY_VALUE["mp3"] == OutputFormat.AUDIO
    assert _FORMAT_BY_VALUE["audio"] == OutputFormat.AUDIO


def test_build_sql_selecciona_identidad_de_recurso() -> None:
    sql, _ = _build_sql(SearchRequest(query="mozart"), 400, use_fulltext=False)
    assert sql is not None
    assert "r.source_rep_id" in sql
    assert "r.resource_id" in sql


def test_row_to_candidate_transporta_identidad_cpdl() -> None:
    """La identidad de edición/recurso viaja en metadata y en el candidate_id."""
    cand = _row_to_candidate(_row(source_rep_id="301", resource_id=392025, format="pdf"))
    assert cand.metadata is not None
    assert cand.metadata["source_rep_id"] == "301"
    assert cand.metadata["resource_id"] == 392025
    assert cand.candidate_id.value == "index-388634-cpdl-392025"
    assert cand.format == OutputFormat.PDF


def test_row_to_candidate_ediciones_distintas_no_colisionan() -> None:
    """Dos ediciones CPDL PDF distintas comparten work/format pero no candidate_id."""
    a = _row_to_candidate(_row(source_rep_id="301", resource_id=392025))
    b = _row_to_candidate(_row(source_rep_id="302", resource_id=392034))
    assert a.candidate_id.value != b.candidate_id.value


def test_row_to_candidate_legacy_sin_identidad() -> None:
    """OMR/IMSLP no tienen edición/recurso: resource_id 0 y sin source_rep_id."""
    cand = _row_to_candidate(_row(provider="omr", format="musicxml", source_rep_id="", resource_id=0))
    assert cand.metadata is not None
    assert cand.metadata["resource_id"] == 0
    assert cand.metadata["source_rep_id"] == ""
    assert cand.candidate_id.value == "index-388634-omr-0"


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


def test_build_sql_filtra_por_genre_id() -> None:
    """El filtro de género (genre_ids) se traduce a `genre_id IN (...)` en el índice."""
    sql, args = _build_sql(
        SearchRequest(query="mozart", genre_ids=(1, 2)), 400, use_fulltext=False
    )
    assert sql is not None
    assert "i.genre_id IN (%s, %s)" in sql
    assert 1 in args
    assert 2 in args


def test_build_sql_sin_genre_ids_no_filtra() -> None:
    sql, args = _build_sql(SearchRequest(query="mozart"), 400, use_fulltext=False)
    assert sql is not None
    assert "genre_id" not in sql
    assert 1 not in args


def test_build_sql_texto_libre_usa_fulltext_con_token_unico() -> None:
    """Un único token >=3 chars sin catálogo usa MATCH (índice FULLTEXT)."""
    sql, args = _build_sql(SearchRequest(query="moz"), 400, use_fulltext=True)
    assert sql is not None
    assert "MATCH(i.title, i.composer_name) AGAINST" in sql
    assert "IN BOOLEAN MODE" in sql
    assert args[0] == "+moz*"


def test_build_sql_texto_libre_sin_fulltext_cae_a_like() -> None:
    """Sin el índice FULLTEXT, la búsqueda libre vuelve a LIKE (fallback seguro)."""
    sql, args = _build_sql(SearchRequest(query="moz"), 400, use_fulltext=False)
    assert sql is not None
    assert "MATCH" not in sql
    assert "title LIKE" in sql
    assert "%moz%" in args


def test_build_sql_texto_libre_multi_palabra_usa_fulltext() -> None:
    """Varias palabras (>=3 chars) usan MATCH BOOLEAN con prefijo por token."""
    sql, args = _build_sql(SearchRequest(query="ave verum"), 400, use_fulltext=True)
    assert sql is not None
    assert "MATCH(i.title, i.composer_name) AGAINST" in sql
    assert args[0] == "+ave* +verum*"


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


def test_build_sql_filtra_por_voices() -> None:
    """El filtro de formación vocal usa la faceta `index_work_voicings` (mayúsculas, dedup)."""
    sql, args = _build_sql(SearchRequest(voices=("SATB", "satb")), 400, use_fulltext=False)
    assert sql is not None
    assert "index_work_voicings" in sql
    assert args.count("SATB") == 1  # deduplicado y normalizado a mayúsculas


def test_build_sql_solo_voices_no_devuelve_vacio() -> None:
    """Buscar solo por formación vocal debe consultar el índice (no (None, ()))."""
    sql, _ = _build_sql(SearchRequest(voices=("SSATB",)), 400, use_fulltext=False)
    assert sql is not None
