from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from src.osap.domain.output_format import OutputFormat
from src.osap.domain.work_descriptor import WorkDescriptor

if TYPE_CHECKING:
    from src.osap.application.execution_plan import WorkGroup


class RankingCriterion(Enum):
    RELEVANCE_TITLE = "relevance_title"
    RELEVANCE_COMPOSER = "relevance_composer"
    RELEVANCE_CATALOGUE = "relevance_catalogue"
    QUALITY_CONFIDENCE = "quality_confidence"
    QUALITY_COMPLETENESS = "quality_completeness"
    PREFERENCE_FORMAT = "preference_format"
    PREFERENCE_LICENSE = "preference_license"
    PREFERENCE_PROVIDER = "preference_provider"
    PREFERENCE_LOCALITY = "preference_locality"
    COVERAGE = "coverage"


class SortingPolicy(Enum):
    STABLE = "stable"
    BY_PROVIDER = "provider"
    BY_TITLE = "title"
    BY_CATALOGUE = "catalogue"


@dataclass(frozen=True)
class RankingReason:
    criterion: RankingCriterion
    field_score: float  # 0..1 (cuánto cumple este criterio)
    weight: float  # peso configurado
    contribution: float  # field_score × weight (explica exactamente el resultado)


@dataclass(frozen=True)
class RankingScore:
    work: "WorkGroup"
    score: float  # Σ contribution, normalizado por los pesos evaluados
    reasons: tuple[RankingReason, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class UserPreferences:
    """What the user wants (independent value object)."""

    desired_format: OutputFormat | None = None
    preferred_license: str | None = None
    allowed_providers: tuple[str, ...] = field(default_factory=tuple)
    prefer_local: bool = False


@dataclass(frozen=True)
class RankingContext:
    """Only what the ranking needs; never the full SearchRequest."""

    query_descriptor: WorkDescriptor
    user_preferences: UserPreferences = UserPreferences()
    execution_context: object | None = None


@dataclass(frozen=True)
class RankingResult:
    context: RankingContext
    order: tuple[RankingScore, ...] = field(default_factory=tuple)
    evaluated_criteria: tuple[RankingCriterion, ...] = field(default_factory=tuple)


_DEFAULT_WEIGHTS: dict[RankingCriterion, float] = {
    RankingCriterion.RELEVANCE_TITLE: 0.25,
    RankingCriterion.RELEVANCE_COMPOSER: 0.30,
    RankingCriterion.RELEVANCE_CATALOGUE: 0.35,
    RankingCriterion.QUALITY_CONFIDENCE: 0.20,
    RankingCriterion.QUALITY_COMPLETENESS: 0.10,
    RankingCriterion.PREFERENCE_FORMAT: 0.20,
    RankingCriterion.PREFERENCE_LICENSE: 0.10,
    RankingCriterion.PREFERENCE_PROVIDER: 0.10,
    RankingCriterion.PREFERENCE_LOCALITY: 0.05,
    RankingCriterion.COVERAGE: 0.05,
}


@dataclass(frozen=True)
class RankingConfig:
    """Policy for ranking (criteria enabled, weights, sorting)."""

    enabled_criteria: tuple[RankingCriterion, ...] = field(
        default_factory=lambda: tuple(RankingCriterion)
    )
    weights: dict[RankingCriterion, float] = field(default_factory=lambda: dict(_DEFAULT_WEIGHTS))
    sorting_policy: SortingPolicy = SortingPolicy.STABLE
