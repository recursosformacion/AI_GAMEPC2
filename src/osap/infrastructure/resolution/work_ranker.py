"""FASE 5.2–5.4 — Ranking y decisión de Work Resolution (dentro del motor).

Separa explícitamente:
    Candidates → Ranking → Best candidate → Confianza → Decision

La decisión no es una fórmula ciega de pesos: usa **señales basadas en evidencia**
descubiertas sobre el baseline de las 250 (multiplicidad de proveedores, margen sobre el
2º candidato, presencia de compositor). Política configurable. No toca contratos ni
arquitectura.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

# Política por defecto (configurable, no cerrada en el ADR).
DEFAULT_MIN_PROVIDERS = 2
DEFAULT_MIN_MARGIN = 0.0


@dataclass(frozen=True)
class RankedCandidate:
    provider: str
    score: float
    identity: dict[str, object]


@dataclass(frozen=True)
class Ranking:
    best: RankedCandidate | None
    second: RankedCandidate | None
    margin: float | None
    matching_providers: int
    candidate_count: int

    @property
    def best_score(self) -> float | None:
        return self.best.score if self.best is not None else None

    @property
    def second_score(self) -> float | None:
        return self.second.score if self.second is not None else None


@dataclass(frozen=True)
class Decision:
    status: str  # resolved | ambiguous | not_found
    reason: str
    ranking: Ranking


def rank(candidates: list[dict[str, object]]) -> Ranking:
    """Ordena por score (provider confidence) y expone best/second/margin/providers."""
    sorted_cands = sorted(
        candidates,
        key=lambda c: float(cast("float", c.get("confidence") or 0)),
        reverse=True,
    )
    best = _ranked(sorted_cands[0]) if sorted_cands else None
    second = _ranked(sorted_cands[1]) if len(sorted_cands) > 1 else None
    margin = (best.score - second.score) if best is not None and second is not None else None
    matching = len({str(c.get("provider") or "?") for c in candidates})
    return Ranking(
        best=best,
        second=second,
        margin=margin,
        matching_providers=matching,
        candidate_count=len(candidates),
    )


def decide(
    candidates: list[dict[str, object]],
    *,
    min_providers: int = DEFAULT_MIN_PROVIDERS,
    min_margin: float = DEFAULT_MIN_MARGIN,
) -> Decision:
    """Decisión evidence-based sobre un grupo de candidatos de una obra."""
    ranking = rank(candidates)
    if ranking.candidate_count == 0:
        return Decision("not_found", "sin candidatos", ranking)

    composer = _composer_of(ranking.best)
    if not composer:
        return Decision("ambiguous", "obra identificada pero compositor no resuelto", ranking)
    if ranking.matching_providers < min_providers:
        return Decision(
            "ambiguous",
            f"evidencia de un solo proveedor ({ranking.matching_providers} < {min_providers})",
            ranking,
        )
    if ranking.margin is not None and ranking.margin < min_margin:
        return Decision(
            "ambiguous",
            f"margen insuficiente sobre el 2º candidato ({ranking.margin:.3f})",
            ranking,
        )
    return Decision(
        "resolved",
        f"candidato dominante con {ranking.matching_providers} proveedores",
        ranking,
    )


def _ranked(candidate: dict[str, object]) -> RankedCandidate:
    identity = candidate.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    return RankedCandidate(
        provider=str(candidate.get("provider") or "?"),
        score=float(cast("float", candidate.get("confidence") or 0)),
        identity=identity,
    )


def _composer_of(candidate: RankedCandidate | None) -> str:
    if candidate is None:
        return ""
    composer = candidate.identity.get("composer")
    return str(composer).strip() if composer else ""
