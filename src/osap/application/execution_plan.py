from dataclasses import dataclass, field

from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.cost_level import CostLevel
from src.osap.domain.value_objects import ProviderId

_COST_RANK: dict[CostLevel, int] = {
    CostLevel.FREE: 0,
    CostLevel.CHEAP: 1,
    CostLevel.NORMAL: 2,
    CostLevel.EXPENSIVE: 3,
}


def cost_rank(level: CostLevel) -> int:
    return _COST_RANK[level]


@dataclass(frozen=True)
class ProviderStep:
    """One step in a provider execution plan.

    `stop_if_found` lets the orchestrator end the search once a sufficient
    provider yields results (e.g. never querying a paid OMR when a FREE source
    already satisfies the request).
    """

    provider_id: ProviderId
    cost_level: CostLevel
    stop_if_found: bool = True


@dataclass(frozen=True)
class ProviderExecutionPlan:
    """Ordered plan of providers to consult, by cost and search relevance."""

    steps: tuple[ProviderStep, ...] = field(default_factory=tuple)
    reused_cache: bool = False


@dataclass(frozen=True)
class ProviderSearchResult:
    """Aggregated result of a provider orchestrated search."""

    candidates: tuple[CandidateRepresentation, ...] = field(default_factory=tuple)
    providers_used: tuple[ProviderId, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    cached: bool = False
