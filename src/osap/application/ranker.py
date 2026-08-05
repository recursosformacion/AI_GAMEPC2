from collections.abc import Iterable
from statistics import fmean
from typing import assert_never

from src.osap.application.execution_plan import WorkGroup
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.normalization import normalize_name
from src.osap.domain.ranking import (
    RankingConfig,
    RankingContext,
    RankingCriterion,
    RankingReason,
    RankingResult,
    RankingScore,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.work_ranker import IWorkRanker

_TITLE_PARTIAL_SCORE = 0.6
_COVERAGE_DENOMINATOR = 3.0


class DefaultWorkRanker(IWorkRanker):
    """Pure, deterministic `IWorkRanker` implementing the frozen contract.

    It never changes identity, never groups, never corrects the WorkMatcher and
    never uses AI. It only computes a score per `WorkGroup` and orders the works.
    """

    def rank(self, works: tuple[WorkGroup, ...], context: RankingContext, config: RankingConfig) -> RankingResult:
        scored = [self._score(work, context, config) for work in works]
        # Stable sort (ties keep the input order). Only SortingPolicy.STABLE is
        # implemented; the rest are prepared for the future.
        scored.sort(key=lambda item: item.score, reverse=True)
        used = {reason.criterion for score in scored for reason in score.reasons}
        evaluated = tuple(criterion for criterion in RankingCriterion if criterion in used)
        return RankingResult(order=tuple(scored), context=context, evaluated_criteria=evaluated)

    def _score(self, work: WorkGroup, context: RankingContext, config: RankingConfig) -> RankingScore:
        reasons: list[RankingReason] = []
        numerator = 0.0
        denominator = 0.0
        for criterion in config.enabled_criteria:
            field_score = _evaluate(criterion, work, context)
            if field_score is None:
                continue  # criterion absent/not applicable: never penalizes
            weight = config.weights.get(criterion, 0.0)
            reasons.append(
                RankingReason(
                    criterion=criterion,
                    field_score=field_score,
                    weight=weight,
                    contribution=field_score * weight,
                )
            )
            numerator += field_score * weight
            denominator += weight
        score = numerator / denominator if denominator > 0 else 0.0
        return RankingScore(work=work, score=score, reasons=tuple(reasons))


def _evaluate(criterion: RankingCriterion, work: WorkGroup, context: RankingContext) -> float | None:
    if criterion is RankingCriterion.RELEVANCE_TITLE:
        return _relevance(_title(context.query_descriptor), _title(work.work))
    if criterion is RankingCriterion.RELEVANCE_COMPOSER:
        return _exact(context.query_descriptor.composer, work.work.composer)
    if criterion is RankingCriterion.RELEVANCE_CATALOGUE:
        return _exact(context.query_descriptor.catalogue_number, work.work.catalogue_number)
    if criterion is RankingCriterion.QUALITY_CONFIDENCE:
        return _average(rep.confidence.value for rep in work.representations)
    if criterion is RankingCriterion.QUALITY_COMPLETENESS:
        return _average(rep.completeness for rep in work.representations)
    if criterion is RankingCriterion.PREFERENCE_FORMAT:
        return _preference_format(work, context)
    if criterion is RankingCriterion.PREFERENCE_LICENSE:
        return _preference_license(work, context)
    if criterion is RankingCriterion.PREFERENCE_PROVIDER:
        return _preference_provider(work, context)
    if criterion is RankingCriterion.PREFERENCE_LOCALITY:
        return _preference_locality(work, context)
    if criterion is RankingCriterion.COVERAGE:
        return _coverage(work)
    assert_never(criterion)


def _title(work: WorkDescriptor) -> str | None:
    value = work.canonical_title or work.title
    return value or None


def _relevance(query: str | None, candidate: str | None) -> float | None:
    if query is None or candidate is None:
        return None
    normalized_query = normalize_name(query)
    normalized_candidate = normalize_name(candidate)
    if normalized_query == normalized_candidate:
        return 1.0
    if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
        return _TITLE_PARTIAL_SCORE
    return 0.0


def _exact(a: str | None, b: str | None) -> float | None:
    if a is None or b is None:
        return None
    return 1.0 if normalize_name(a) == normalize_name(b) else 0.0


def _average(values: Iterable[float]) -> float | None:
    iterator = list(values)
    if not iterator:
        return None
    return fmean(iterator)


def _preference_format(work: WorkGroup, context: RankingContext) -> float | None:
    desired = context.user_preferences.desired_format
    if desired is None:
        return None
    return 1.0 if any(rep.format is desired for rep in work.representations) else 0.0


def _preference_license(work: WorkGroup, context: RankingContext) -> float | None:
    preferred = context.user_preferences.preferred_license
    if not preferred:
        return None
    lowered = preferred.lower()
    return 1.0 if any(_license_ok(rep, lowered) for rep in work.representations) else 0.0


def _preference_provider(work: WorkGroup, context: RankingContext) -> float | None:
    allowed = context.user_preferences.allowed_providers
    if not allowed:
        return None
    return 1.0 if any(rep.provider_id.value in allowed for rep in work.representations) else 0.0


def _preference_locality(work: WorkGroup, context: RankingContext) -> float | None:
    if not context.user_preferences.prefer_local:
        return None
    return 1.0 if any(rep.local_path is not None for rep in work.representations) else 0.0


def _coverage(work: WorkGroup) -> float | None:
    if not work.representations:
        return None
    distinct = len({rep.format for rep in work.representations})
    return min(1.0, distinct / _COVERAGE_DENOMINATOR)


def _license_ok(rep: CandidateRepresentation, preferred: str) -> bool:
    return bool(
        (rep.license is not None and preferred in rep.license.lower())
        or (preferred == "public domain" and rep.public_domain)
    )
