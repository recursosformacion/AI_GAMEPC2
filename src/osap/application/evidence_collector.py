from statistics import fmean

from src.osap.domain.evidence import (
    Evidence,
    EvidenceCode,
    EvidenceField,
    EvidenceItem,
    EvidenceResult,
    EvidenceSource,
    EvidenceStrength,
    EvidenceSummary,
)
from src.osap.domain.matching import MatchField, MatchReason, MatchResult
from src.osap.domain.ranking import RankingCriterion, RankingResult
from src.osap.ports.evidence_collector import IEvidenceCollector
from src.osap.ports.evidence_contributor import IEvidenceContributor


def _match_code(field: MatchField) -> EvidenceCode | None:
    mapping = {
        MatchField.CATALOGUE: EvidenceCode.CATALOGUE_MATCH,
        MatchField.COMPOSER: EvidenceCode.COMPOSER_MATCH,
        MatchField.TITLE: EvidenceCode.TITLE_MATCH,
        MatchField.WORK_AUTHORITY: EvidenceCode.WORK_AUTHORITY_MATCH,
        MatchField.KEY: EvidenceCode.KEY_MATCH,
    }
    return mapping.get(field)


def _rank_code(criterion: RankingCriterion) -> EvidenceCode | None:
    mapping = {
        RankingCriterion.RELEVANCE_TITLE: EvidenceCode.RELEVANCE,
        RankingCriterion.RELEVANCE_COMPOSER: EvidenceCode.RELEVANCE,
        RankingCriterion.RELEVANCE_CATALOGUE: EvidenceCode.RELEVANCE,
        RankingCriterion.QUALITY_CONFIDENCE: EvidenceCode.QUALITY_CONFIDENCE,
        RankingCriterion.QUALITY_COMPLETENESS: EvidenceCode.QUALITY_COMPLETENESS,
        RankingCriterion.PREFERENCE_FORMAT: EvidenceCode.PREFERRED_FORMAT,
        RankingCriterion.PREFERENCE_LICENSE: EvidenceCode.PREFERRED_LICENSE,
        RankingCriterion.COVERAGE: EvidenceCode.COVERAGE,
    }
    return mapping.get(criterion)


def _strength(code: EvidenceCode) -> EvidenceStrength:
    if code is EvidenceCode.WORK_AUTHORITY_MATCH:
        return EvidenceStrength.CRITICAL
    if code in (
        EvidenceCode.CATALOGUE_MATCH,
        EvidenceCode.COMPOSER_MATCH,
        EvidenceCode.TITLE_MATCH,
        EvidenceCode.KEY_MATCH,
        EvidenceCode.RELEVANCE,
        EvidenceCode.SELECTED_REPRESENTATION,
    ):
        return EvidenceStrength.STRONG
    if code in (EvidenceCode.QUALITY_CONFIDENCE, EvidenceCode.QUALITY_COMPLETENESS, EvidenceCode.COVERAGE):
        return EvidenceStrength.NORMAL
    return EvidenceStrength.WEAK


class MatchEvidenceContributor(IEvidenceContributor):
    """Adapts a `MatchResult` into `EvidenceItem` (source=MATCHER)."""

    def __init__(self, match: MatchResult) -> None:
        self._match = match

    def to_evidence(self) -> tuple[EvidenceItem, ...]:
        items: list[EvidenceItem] = []
        for reason in self._match.reasons:
            code = _match_code(reason.field)
            if code is None:
                continue
            fields = _reason_fields(reason)
            items.append(
                EvidenceItem(
                    source=EvidenceSource.MATCHER,
                    code=code,
                    score=reason.field_score,
                    strength=_strength(code),
                    fields=fields,
                )
            )
        return tuple(items)


class RankingEvidenceContributor(IEvidenceContributor):
    """Adapts a `RankingResult` into `EvidenceItem` (source=RANKER)."""

    def __init__(self, ranking: RankingResult) -> None:
        self._ranking = ranking

    def to_evidence(self) -> tuple[EvidenceItem, ...]:
        items: list[EvidenceItem] = []
        for score in self._ranking.order:
            for reason in score.reasons:
                code = _rank_code(reason.criterion)
                if code is None:
                    continue
                fields = (EvidenceField("weight", reason.weight), EvidenceField("contribution", reason.contribution))
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.RANKER,
                        code=code,
                        score=reason.field_score,
                        strength=_strength(code),
                        fields=fields,
                    )
                )
        return tuple(items)


class SelectionEvidenceContributor(IEvidenceContributor):
    """Adapts the selection `Evidence` into `EvidenceItem` (source=SELECTION)."""

    def __init__(self, evidence: Evidence) -> None:
        self._evidence = evidence

    def to_evidence(self) -> tuple[EvidenceItem, ...]:
        items: list[EvidenceItem] = []
        for reason in self._evidence.reasons:
            fields = (EvidenceField("kind", reason.kind.value), EvidenceField("detail", reason.detail))
            items.append(
                EvidenceItem(
                    source=EvidenceSource.SELECTION,
                    code=EvidenceCode.SELECTED_REPRESENTATION,
                    score=1.0 if reason.satisfied else 0.0,
                    strength=_strength(EvidenceCode.SELECTED_REPRESENTATION),
                    fields=fields,
                )
            )
        return tuple(items)


def _reason_fields(reason: MatchReason) -> tuple[EvidenceField, ...]:
    fields: list[EvidenceField] = []
    if reason.left is not None:
        fields.append(EvidenceField("left", reason.left))
    if reason.right is not None:
        fields.append(EvidenceField("right", reason.right))
    return tuple(fields)


def _mean(values: list[float]) -> float:
    return fmean(values) if values else 0.0


class DefaultEvidenceCollector(IEvidenceCollector):
    """Collects `EvidenceItem`s from contributors and aggregates them."""

    def collect(self, contributors: tuple[IEvidenceContributor, ...]) -> EvidenceResult:
        items: list[EvidenceItem] = []
        for contributor in contributors:
            items.extend(contributor.to_evidence())
        matcher_score = _mean([item.score for item in items if item.source is EvidenceSource.MATCHER])
        ranking_score = _mean([item.score for item in items if item.source is EvidenceSource.RANKER])
        selection_score = _mean([item.score for item in items if item.source is EvidenceSource.SELECTION])
        overall_score = _mean([item.score for item in items])
        summary = EvidenceSummary(
            matcher_score=matcher_score,
            ranking_score=ranking_score,
            selection_score=selection_score,
            overall_score=overall_score,
        )
        return EvidenceResult(items=tuple(items), summary=summary, overall_score=overall_score)
