"""FASE 5.2–5.4 — ranking y decisión de Work Resolution (dentro del motor).

Verifica la separación Ranking → Best → Decision y que la decisión evidencia-based
degrada a `ambiguous` los casos dudosos (un solo proveedor, margen insuficiente,
compositor no resuelto) para evitar falsos resolved.
"""

from __future__ import annotations

from src.osap.infrastructure.resolution.work_ranker import decide, rank


def _cand(provider: str, confidence: float, composer: str = "Wolfgang Amadeus Mozart") -> dict[str, object]:
    return {"provider": provider, "confidence": confidence, "identity": {"composer": composer}}


def test_no_candidates_is_not_found() -> None:
    d = decide([])
    assert d.status == "not_found"


def test_single_provider_resolved_becomes_ambiguous() -> None:
    # El patrón descubierto: los 72 falsos resolved eran 1 candidato / 1 proveedor.
    d = decide([_cand("omr", 0.9)])
    assert d.status == "ambiguous"
    assert "un solo proveedor" in d.reason


def test_two_providers_equal_with_composer_resolved() -> None:
    d = decide([_cand("omr", 0.9), _cand("imslp", 0.9)])
    assert d.status == "resolved"
    assert d.ranking.matching_providers == 2


def test_missing_composer_is_ambiguous() -> None:
    cands = [_cand("omr", 0.9, composer=""), _cand("imslp", 0.9, composer="")]
    d = decide(cands)
    assert d.status == "ambiguous"
    assert "compositor" in d.reason


def test_small_margin_is_ambiguous() -> None:
    cands = [_cand("omr", 0.93), _cand("imslp", 0.91)]
    d = decide(cands, min_margin=0.05)
    assert d.status == "ambiguous"
    assert "margen" in d.reason


def test_clear_margin_resolved() -> None:
    cands = [_cand("omr", 0.93), _cand("imslp", 0.41)]
    d = decide(cands, min_margin=0.05)
    assert d.status == "resolved"
    assert d.ranking.best_score == 0.93
    assert d.ranking.second_score == 0.41
    assert d.ranking.margin == 0.52


def test_ranking_exposes_best_second_margin() -> None:
    r = rank([_cand("omr", 0.9), _cand("imslp", 0.41), _cand("mb", 0.41)])
    assert r.best_score == 0.9
    assert r.second_score == 0.41
    assert r.margin is not None and abs(r.margin - 0.49) < 1e-9
    assert r.matching_providers == 3
    assert r.candidate_count == 3
