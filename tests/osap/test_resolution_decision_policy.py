"""F3.3 — ResolutionDecisionPolicy: reglas ADR-0034 + paridad con decide() (250 obras).

La política es pura y determinista. Su paridad se verifica contra la heurística actual
`work_ranker.decide()` (que se mantiene como referencia durante la transición).
"""

import itertools
import json
from pathlib import Path

import pytest

from src.osap.application.resolution_decision import (
    STATUS_AMBIGUOUS,
    STATUS_NOT_FOUND,
    STATUS_RESOLVED,
    DecisionConfig,
    ResolutionCandidate,
    ResolutionDecisionPolicy,
)
from src.osap.infrastructure.resolution.work_ranker import decide as legacy_decide

_CORPUS = Path(__file__).resolve().parents[2] / "script" / "works250.results.json"

_PROVIDERS = ("omr", "imslp", "mutopia", "mb")
_CONFIDENCES = (0.9, 0.8, 0.5, 0.3)
_COMPOSERS = ("Mozart", "Fake", "")


def _policy(min_providers: int = 2, min_margin: float = 0.0) -> ResolutionDecisionPolicy:
    return ResolutionDecisionPolicy(DecisionConfig(min_matching_providers=min_providers, min_margin=min_margin))


def _cand(provider: str, confidence: float, composer: str | None = "Mozart") -> ResolutionCandidate:
    return ResolutionCandidate(provider=provider, confidence=confidence, composer=composer)


def _legacy_cand(c: ResolutionCandidate) -> dict[str, object]:
    return {"provider": c.provider, "confidence": c.confidence, "identity": {"composer": c.composer}}


# --- reglas básicas ---------------------------------------------------------


def test_no_candidates_is_not_found() -> None:
    decision = _policy().decide(())
    assert decision.status == STATUS_NOT_FOUND
    assert decision.ranking.candidate_count == 0


def test_single_provider_with_composer_is_ambiguous() -> None:
    decision = _policy().decide((_cand("omr", 0.9),))
    assert decision.status == STATUS_AMBIGUOUS


def test_two_providers_with_composer_and_clear_best_is_resolved() -> None:
    decision = _policy().decide((_cand("omr", 0.9), _cand("imslp", 0.9)))
    assert decision.status == STATUS_RESOLVED
    assert decision.ranking.matching_providers == 2


def test_composer_alone_never_resolves() -> None:
    # ADR-0034: tener compositor no basta; hace falta evidencia (≥2 proveedores).
    assert _policy().decide((_cand("omr", 0.99),)).status == STATUS_AMBIGUOUS


def test_missing_composer_is_ambiguous_not_anonymous() -> None:
    decision = _policy().decide((_cand("omr", 0.9, None), _cand("imslp", 0.9, None)))
    assert decision.status == STATUS_AMBIGUOUS
    assert "compositor" in decision.reason
    assert "anonymous" not in decision.reason.lower()
    assert "traditional" not in decision.reason.lower()


def test_group_composer_can_backfill_missing_candidate_attribution() -> None:
    decision = _policy().decide(
        (_cand("omr", 0.9, None), _cand("imslp", 0.9, None)),
        group_composer="Wolfgang Amadeus Mozart",
    )
    assert decision.status == STATUS_RESOLVED


def test_small_margin_is_ambiguous_when_configured() -> None:
    decision = _policy(min_margin=0.05).decide((_cand("omr", 0.93), _cand("imslp", 0.91)))
    assert decision.status == STATUS_AMBIGUOUS
    assert "margen" in decision.reason


def test_clear_margin_is_resolved() -> None:
    decision = _policy(min_margin=0.05).decide((_cand("omr", 0.93), _cand("imslp", 0.41)))
    assert decision.status == STATUS_RESOLVED
    assert decision.ranking.best_score == 0.93
    assert decision.ranking.second_score == 0.41
    assert decision.ranking.margin is not None and abs(decision.ranking.margin - 0.52) < 1e-9


def test_decision_is_deterministic_and_order_independent() -> None:
    cands = (_cand("omr", 0.8), _cand("imslp", 0.9), _cand("mutopia", 0.7))
    first = _policy().decide(cands)
    second = _policy().decide(tuple(reversed(cands)))
    assert first.status == second.status == STATUS_RESOLVED
    assert first.ranking.best_score == second.ranking.best_score == 0.9


# --- paridad exhaustiva sintética con decide() ------------------------------


def test_synthetic_parity_with_legacy_decide() -> None:
    policy = _policy()
    # Combinaciones de 0..4 candidatos sobre un grid fijo de proveedor/confianza/compositor.
    grid = list(itertools.product(_PROVIDERS, _CONFIDENCES, _COMPOSERS))[:24]
    combos: list[tuple[ResolutionCandidate, ...]] = []
    for size in range(0, 5):
        for selected in itertools.combinations(grid, size):
            combos.append(
                tuple(ResolutionCandidate(provider=p, confidence=c, composer=(name or None)) for p, c, name in selected)
            )
            if len(combos) >= 4000:
                break
        if len(combos) >= 4000:
            break

    assert combos
    for candidates in combos:
        new_status = policy.decide(candidates).status
        legacy_status = legacy_decide([_legacy_cand(c) for c in candidates]).status
        assert new_status == legacy_status, f"parity mismatch for {candidates!r}"


# --- paridad sobre el corpus de las 250 obras -------------------------------


def _corpus_results() -> list[dict[str, object]] | None:
    if not _CORPUS.exists():
        return None
    doc = json.loads(_CORPUS.read_text(encoding="utf-8"))
    results = doc.get("results") if isinstance(doc, dict) else None
    return results if isinstance(results, list) else None


def test_corpus_parity_with_legacy_decide() -> None:
    results = _corpus_results()
    if results is None:
        pytest.skip("works250.results.json no disponible")
    assert len(results) >= 200

    policy = _policy()
    mismatches: list[str] = []
    for r in results:
        resolved = r.get("resolved") or {}
        composer_raw = resolved.get("composer")
        composer = (
            composer_raw.get("name") if isinstance(composer_raw, dict) else composer_raw
        )
        candidates: list[ResolutionCandidate] = []
        for e in r.get("evidence") or []:
            if not isinstance(e, dict):
                continue
            candidates.append(
                ResolutionCandidate(
                    provider=str(e.get("provider") or "?"),
                    confidence=float(e.get("confidence") or 0.0),
                    composer=str(composer) if composer else None,
                )
            )
        new_status = policy.decide(tuple(candidates)).status
        legacy_status = legacy_decide(
            [
                {
                    "provider": c.provider,
                    "confidence": c.confidence,
                    "identity": {"composer": c.composer},
                }
                for c in candidates
            ]
        ).status
        if new_status != legacy_status:
            mismatches.append(str(r.get("id")))
    assert not mismatches, f"discrepancias de paridad en ids: {mismatches[:20]}"


def test_corpus_decision_distribution_is_sane() -> None:
    results = _corpus_results()
    if results is None:
        pytest.skip("works250.results.json no disponible")
    policy = _policy()
    counts = {STATUS_RESOLVED: 0, STATUS_AMBIGUOUS: 0, STATUS_NOT_FOUND: 0}
    for r in results:
        resolved = r.get("resolved") or {}
        composer_raw = resolved.get("composer")
        composer = composer_raw.get("name") if isinstance(composer_raw, dict) else composer_raw
        candidates = tuple(
            ResolutionCandidate(
                provider=str(e.get("provider") or "?"),
                confidence=float(e.get("confidence") or 0.0),
                composer=str(composer) if composer else None,
            )
            for e in (r.get("evidence") or [])
            if isinstance(e, dict)
        )
        counts[policy.decide(candidates).status] += 1
    assert counts[STATUS_NOT_FOUND] > 0
    assert counts[STATUS_RESOLVED] > 0
    assert counts[STATUS_AMBIGUOUS] > 0
