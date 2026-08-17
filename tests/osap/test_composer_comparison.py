"""FASE 5.6 — canonicalización de compositor para matching.

Verifica que la clave de comparación colapsa variantes del mismo compositor (nombres
completos/iniciales, años sueltos) y unifica marcadores genéricos, sin alterar la forma
para mostrar (`canonical_composer`).
"""

from __future__ import annotations

from src.osap.application.metadata_normalizer import MetadataNormalizer


def _same(a: str, b: str) -> bool:
    ka, kb = MetadataNormalizer.comparison_composer(a), MetadataNormalizer.comparison_composer(b)
    return bool(ka) and ka == kb


def test_full_vs_initials_collapse() -> None:
    assert _same("Edmund Simon Lorenz", "Edmund S. Lorenz")


def test_trailing_year_collapse() -> None:
    assert _same("Edmund Simon Lorenz 1886", "Edmund S. Lorenz")


def test_middle_name_initial_collapse() -> None:
    assert _same("Charles Hutchinson Gabriel", "Charles H. Gabriel")


def test_anon_trad_unify_to_anonymous() -> None:
    assert _same("anon", "Anonymous")
    assert _same("Trad", "Traditional")
    assert MetadataNormalizer.comparison_composer("anon") == "anonymous"


def test_urheber_unbekannt_is_anonymous() -> None:
    # "Urheber unbekannt" = autor desconocido (alemán), con basura concatenada.
    assert MetadataNormalizer.comparison_composer("Urheber unbekannt") == "anonymous"
    assert (
        MetadataNormalizer.comparison_composer(
            "Urheber unbekanntDatum in der hier transkribierten schriftlichen Quelle: 1796"
        )
        == "anonymous"
    )
    assert _same("Urheber unbekannt", "anon")


def test_distinct_composers_stay_distinct() -> None:
    assert not _same("Edmund S. Lorenz", "Charles H. Gabriel")


def test_display_form_unchanged() -> None:
    # La forma para mostrar sigue intacta; solo la clave de comparación colapsa.
    assert MetadataNormalizer.canonical_composer("Edmund Simon Lorenz 1886") != MetadataNormalizer.canonical_composer(
        "Edmund S. Lorenz"
    )


def test_extract_composer_from_title_dash() -> None:
    assert MetadataNormalizer.extract_composer_from_title("Joy-bells - Charles H. Gabriel") == (
        "Joy-bells",
        "Charles H. Gabriel",
    )


def test_extract_composer_from_title_by() -> None:
    assert MetadataNormalizer.extract_composer_from_title("Ave Verum Corpus by Mozart") == (
        "Ave Verum Corpus",
        "Mozart",
    )


def test_extract_composer_from_title_none_when_absent() -> None:
    assert MetadataNormalizer.extract_composer_from_title("Trunch Wassail Song") == ("Trunch Wassail Song", None)


def test_normalize_title_catalog_suffix() -> None:
    n = MetadataNormalizer.normalize_title_with_trace("Trip Up Stairs. Ru1.183 A")
    assert n.key == "trip up stairs"
    assert any(r["reason"] == "catalog_reference" for r in n.removed)


def test_normalize_title_leading_article() -> None:
    n = MetadataNormalizer.normalize_title_with_trace("The Regency Waltz")
    assert n.key == "regency waltz"
    assert any(r["reason"] == "leading_article" for r in n.removed)


def test_normalize_title_traceable_not_destructive() -> None:
    n = MetadataNormalizer.normalize_title_with_trace("God Save The King. HSJJ.188")
    assert n.key == "god save the king"
    assert n.raw == "God Save The King. HSJJ.188"  # no destruye el original
    reasons = {r["reason"] for r in n.removed}
    assert "catalog_reference" in reasons


def test_normalize_title_keeps_distinct_works() -> None:
    # Sin ruido conocido: NO deben agruparse.
    queen = MetadataNormalizer.normalize_title_with_trace("God Save the Queen").key
    modulation = MetadataNormalizer.normalize_title_with_trace("Modulation on God Save the King").key
    king = MetadataNormalizer.normalize_title_with_trace("God Save the King").key
    assert queen != king
    assert modulation != king


def test_normalize_title_attribution_as_evidence_only() -> None:
    # Con el compositor como evidencia, la atribución se separa de la identidad.
    n = MetadataNormalizer.normalize_title_with_trace("God Save the King - Thomas Arne", "Thomas Arne")
    assert n.key == "god save the king"
    assert n.attribution == "Thomas Arne"
    # Sin compositor (sin evidencia), no se destruye el título.
    n2 = MetadataNormalizer.normalize_title_with_trace("God Save the King - Thomas Arne")
    assert "thomas arne" in n2.key
