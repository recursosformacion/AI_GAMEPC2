"""Tests de los slugs SEO (URLs públicas de compositor y obra)."""

from __future__ import annotations

from src.osap.api.seo.slug import (
    normalize_work_id,
    person_slug,
    slugify,
    work_canonical_slug,
    work_slug,
)


def test_slugify_quita_acentos_y_normaliza_separadores() -> None:
    assert slugify("Ave verum corpus, KV 618") == "ave-verum-corpus-kv-618"
    assert slugify("Wolff, Hugo (1888–1960)") == "wolff-hugo-1888-1960"
    assert slugify("  Johann   Sebastian   Bach  ") == "johann-sebastian-bach"


def test_slugify_sin_alfanumericos_devuelve_vacio() -> None:
    assert slugify("¿?—…") == ""
    assert slugify("") == ""


def test_slugify_translitera_ligaduras_y_letras_no_ascii() -> None:
    assert slugify("Œuvre pour Æther") == "oeuvre-pour-aether"
    assert slugify("Straße") == "strasse"
    assert slugify("Ørsted") == "orsted"


def test_work_y_person_slug_tienen_fallback_estable() -> None:
    assert work_slug("Ave verum corpus") == "ave-verum-corpus"
    assert work_slug("") == "obra"
    assert person_slug("Mozart") == "mozart"
    assert person_slug("") == "compositor"


def test_work_canonical_slug_usa_solo_titulo() -> None:
    # El compositor NO se concatena (los títulos CPDL ya lo incluyen: evita el duplicado
    # `-martin-luther-martin-luther` y el churn de URLs que generaba 301).
    assert work_canonical_slug("The mouth of fools doth God confess - Martin Luther") == (
        "the-mouth-of-fools-doth-god-confess-martin-luther"
    )
    assert work_canonical_slug("Ave verum corpus") == "ave-verum-corpus"
    assert work_canonical_slug("") == "obra"


def test_normalize_work_id_acepta_index_y_numerico() -> None:
    assert normalize_work_id("index-123") == "index-123"
    assert normalize_work_id("123") == "index-123"
    assert normalize_work_id("index-000123") == "index-123"
    assert normalize_work_id("index-abc") is None
    assert normalize_work_id("indice-1") is None
