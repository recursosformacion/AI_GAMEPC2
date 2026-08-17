"""Primer paso — cruzar la obra por título ignorando el compositor faltante.

La misma obra puede llegar con `composer=None` (OMR) y con compositor (IMSLP). El matcher
debe agruparlas por título y adoptar el compositor si al menos un registro lo tiene. Un
compositor incrustado en el título se extrae. Nunca se asume anónimo.
"""

from __future__ import annotations

from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher


def _w(provider: str, title: str, composer: str | None = None, confidence: float = 0.9) -> dict[str, object]:
    identity: dict[str, object] = {"id": f"{provider}-{title}", "title": title, "confidence": confidence}
    if composer:
        identity["composer"] = composer
    return {"provider": provider, "work": {"identity": identity}}


def test_omr_without_composer_merges_with_imslp_that_has_it() -> None:
    universe = [
        _w("omr", "Trip it up Stairs. JJo4.133"),  # composer=None
        _w("imslp", "Trip it up Stairs. JJo4.133", "John Liptrot Hatton"),
    ]
    items = SimpleUniverseMatcher().match(universe)
    assert len(items) == 1  # una sola obra, no dos
    assert items[0]["status"] == "resolved"
    assert items[0]["resolved"]["composer"]["name"] is not None


def test_composer_extracted_from_title() -> None:
    universe = [_w("omr", "Joy-bells - Charles H. Gabriel")]  # sin campo composer
    items = SimpleUniverseMatcher().match(universe)
    assert len(items) == 1
    # El compositor viene del título.
    assert items[0]["resolved"]["composer"] is not None


def test_no_composer_anywhere_is_unknown_not_anonymous() -> None:
    universe = [_w("omr", "Trunch Wassail Song")]
    items = SimpleUniverseMatcher().match(universe)
    assert len(items) == 1
    # La obra se identifica pero el compositor queda desconocido (ambiguous, no not_found).
    assert items[0]["status"] == "ambiguous"
    assert items[0]["resolved"]["composer"] is None


def test_two_distinct_composers_same_title_is_ambiguous() -> None:
    universe = [
        _w("imslp", "Ave Verum", "Mozart"),
        _w("imslp", "Ave Verum", "Byrd"),
    ]
    items = SimpleUniverseMatcher().match(universe)
    assert len(items) == 1
    assert items[0]["status"] == "ambiguous"
