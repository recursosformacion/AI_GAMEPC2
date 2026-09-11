"""ResolutionDecisionPolicy — decisión pura resolved|ambiguous|not_found (F3.3).

Sustituye conceptualmente a la heurística por dicts de `work_ranker.decide()` con una
política pura y determinista que consume candidatos tipados. Reglas ADR-0034:

- `composer=None` nunca se interpreta como Anonymous/Traditional: obra identificada sin
  atribución → `ambiguous`.
- Tener compositor no basta para `resolved`: se exige además evidencia suficiente
  (multiplicidad de proveedores y, si está configurado, margen sobre el 2º candidato).

No conoce adquisición, persistencia, HTTP ni estado de sesión. La paridad con `decide()`
sobre el corpus de las 250 obras se verifica en tests (`test_resolution_decision_policy`).
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MIN_MATCHING_PROVIDERS = 2
DEFAULT_MIN_MARGIN = 0.0

STATUS_RESOLVED = "resolved"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ResolutionCandidate:
    """Vista mínima y tipada de un candidato para la decisión de resolución."""

    provider: str
    confidence: float
    # Atribución efectiva del candidato (la consolida quien agrupa: proveedor o título).
    composer: str | None = None


@dataclass(frozen=True)
class DecisionRanking:
    """Resultado de ordenar los candidatos: best/second/margin/proveedores."""

    best: ResolutionCandidate | None
    second: ResolutionCandidate | None
    margin: float | None
    matching_providers: int
    candidate_count: int

    @property
    def best_score(self) -> float | None:
        return self.best.confidence if self.best is not None else None

    @property
    def second_score(self) -> float | None:
        return self.second.confidence if self.second is not None else None


@dataclass(frozen=True)
class ResolutionDecision:
    status: str  # resolved | ambiguous | not_found
    reason: str
    ranking: DecisionRanking


@dataclass(frozen=True)
class DecisionConfig:
    min_matching_providers: int = DEFAULT_MIN_MATCHING_PROVIDERS
    min_margin: float = DEFAULT_MIN_MARGIN


class ResolutionDecisionPolicy:
    """Reglas de decisión por grupo de obra, puras y deterministas (ADR-0034)."""

    def __init__(self, config: DecisionConfig | None = None) -> None:
        self._config = config or DecisionConfig()

    def decide(
        self,
        candidates: tuple[ResolutionCandidate, ...],
        *,
        group_composer: str | None = None,
    ) -> ResolutionDecision:
        """Decide el estado de un grupo.

        `group_composer` es la atribución consolidada del grupo (si el agrupador la resolvió
        desde algún miembro o del título); nunca la inventa esta política.
        """
        ranking = self._rank(candidates)
        if ranking.candidate_count == 0:
            return ResolutionDecision(STATUS_NOT_FOUND, "sin candidatos", ranking)

        best_composer = self._effective_composer(ranking.best, group_composer)
        if not best_composer:
            return ResolutionDecision(
                STATUS_AMBIGUOUS, "obra identificada pero compositor no resuelto", ranking
            )
        if ranking.matching_providers < self._config.min_matching_providers:
            return ResolutionDecision(
                STATUS_AMBIGUOUS,
                f"evidencia de un solo proveedor "
                f"({ranking.matching_providers} < {self._config.min_matching_providers})",
                ranking,
            )
        if ranking.margin is not None and ranking.margin < self._config.min_margin:
            return ResolutionDecision(
                STATUS_AMBIGUOUS,
                f"margen insuficiente sobre el 2º candidato ({ranking.margin:.3f})",
                ranking,
            )
        return ResolutionDecision(
            STATUS_RESOLVED,
            f"candidato dominante con {ranking.matching_providers} proveedores",
            ranking,
        )

    @staticmethod
    def _rank(candidates: tuple[ResolutionCandidate, ...]) -> DecisionRanking:
        ordered = sorted(candidates, key=lambda c: c.confidence, reverse=True)
        best = ordered[0] if ordered else None
        second = ordered[1] if len(ordered) > 1 else None
        margin = (
            best.confidence - second.confidence
            if best is not None and second is not None
            else None
        )
        return DecisionRanking(
            best=best,
            second=second,
            margin=margin,
            matching_providers=len({c.provider for c in candidates}),
            candidate_count=len(candidates),
        )

    @staticmethod
    def _effective_composer(
        best: ResolutionCandidate | None, group_composer: str | None
    ) -> str | None:
        if best is None:
            return None
        value = best.composer or group_composer
        if value is None:
            return None
        text = value.strip()
        return text if text else None


__all__ = [
    "DecisionConfig",
    "DecisionRanking",
    "ResolutionCandidate",
    "ResolutionDecision",
    "ResolutionDecisionPolicy",
    "STATUS_RESOLVED",
    "STATUS_AMBIGUOUS",
    "STATUS_NOT_FOUND",
]
