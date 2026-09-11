"""Universe resolver V2.1 — contrato y composición de la pipeline canónica (F3.4).

`IUniverseResolver` encapsula la resolución técnica de un universo de candidatos tipados:

    Matcher (identidad) → agrupación → DefaultWorkRanker → DefaultMergeService

y produce un resultado rico por grupo (identidad + ranking + consolidación + evidencia),
sobre el que después actúa `ResolutionDecisionPolicy` (estado resolved|ambiguous|not_found).

Este resolver NO conoce: HTTP, persistencia, sesiones, JWT, AcquisitionService ni JSON de
infraestructura. No decide estado; solo responde «qué representa este universo».
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.osap.application.matcher import DefaultWorkMatcher
from src.osap.application.merge_service import DefaultMergeService
from src.osap.application.ranker import DefaultWorkRanker
from src.osap.domain.matching import MatchingConfig, MatchLevel
from src.osap.domain.merge import MergePolicy
from src.osap.domain.ranking import RankingContext, RankingPolicy, UserPreferences
from src.osap.domain.value_objects import ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.domain.work_group import WorkGroup

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation
    from src.osap.domain.merge import MergeResult
    from src.osap.domain.ranking import RankingCriterion, RankingScore


@dataclass(frozen=True)
class ResolvedGroup:
    """Resultado técnico por obra: identidad agrupada + ranking + consolidación."""

    group: WorkGroup
    score: RankingScore
    merged: MergeResult


@dataclass(frozen=True)
class UniverseResolutionResult:
    groups: tuple[ResolvedGroup, ...]
    evaluated_criteria: tuple[RankingCriterion, ...] = ()


class IUniverseResolver(Protocol):
    def resolve(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        *,
        query: WorkDescriptor | None = None,
        user_preferences: UserPreferences | None = None,
    ) -> UniverseResolutionResult:
        ...


class V21UniverseResolver:
    """Resuelve el universo con la pipeline V2.1 pura (dominio/aplicación)."""

    def __init__(
        self,
        *,
        matching_config: MatchingConfig | None = None,
        ranking_policy: RankingPolicy | None = None,
        merge_policy: MergePolicy | None = None,
        matcher: DefaultWorkMatcher | None = None,
        ranker: DefaultWorkRanker | None = None,
        merge_service: DefaultMergeService | None = None,
    ) -> None:
        self._matching_config = matching_config or MatchingConfig()
        self._ranking_policy = ranking_policy or RankingPolicy()
        self._merge_policy = merge_policy or MergePolicy()
        self._matcher = matcher or DefaultWorkMatcher(self._matching_config)
        self._ranker = ranker or DefaultWorkRanker()
        self._merge_service = merge_service or DefaultMergeService()

    def resolve(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        *,
        query: WorkDescriptor | None = None,
        user_preferences: UserPreferences | None = None,
    ) -> UniverseResolutionResult:
        groups = self._cluster(candidates)
        context = RankingContext(
            query_descriptor=query or _neutral_descriptor(),
            user_preferences=user_preferences or UserPreferences(),
        )
        ranking = self._ranker.rank(groups, context, self._ranking_policy)
        resolved: list[ResolvedGroup] = []
        for score in ranking.order:
            merged = self._merge_service.merge(score.work, self._merge_policy)
            resolved.append(ResolvedGroup(group=score.work, score=score, merged=merged))
        return UniverseResolutionResult(
            groups=tuple(resolved),
            evaluated_criteria=ranking.evaluated_criteria,
        )

    def _cluster(self, candidates: tuple[CandidateRepresentation, ...]) -> tuple[WorkGroup, ...]:
        """Agrupa por identidad (MatchLevel.SAME del matcher puro). Orden estable."""
        clusters: list[list[CandidateRepresentation]] = []
        for candidate in candidates:
            placed = False
            for cluster in clusters:
                decision = self._matcher.match(
                    cluster[0].work_descriptor, candidate.work_descriptor
                )
                if decision.level is MatchLevel.SAME:
                    cluster.append(candidate)
                    placed = True
                    break
            if not placed:
                clusters.append([candidate])
        groups: list[WorkGroup] = []
        for cluster in clusters:
            ordered = sorted(cluster, key=_candidate_key)
            groups.append(
                WorkGroup(
                    work=ordered[0].work_descriptor,
                    representations=tuple(ordered),
                    providers=tuple(ProviderId(c.provider_id.value) for c in ordered),
                )
            )
        # Orden de agrupación determinista (independiente del orden de entrada).
        groups.sort(key=lambda g: (_work_key(g.work), _candidate_key(g.representations[0])))
        return tuple(groups)


def _neutral_descriptor() -> WorkDescriptor:
    return WorkDescriptor(work_id=WorkId("neutral"), title="-")


def _candidate_key(candidate: CandidateRepresentation) -> tuple[object, ...]:
    return (
        candidate.provider_id.value,
        candidate.remote_id or candidate.candidate_id.value,
    )


def _work_key(work: WorkDescriptor) -> str:
    return (
        work.canonical_key
        or work.canonical_title
        or (work.title or "").strip().lower()
        or "?"
    ) + "|" + (work.composer or "").strip().lower()


__all__ = [
    "IUniverseResolver",
    "ResolvedGroup",
    "UniverseResolutionResult",
    "V21UniverseResolver",
]
