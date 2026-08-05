from typing import TYPE_CHECKING, assert_never, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

from src.osap.domain.matching import (
    Authority,
    FieldComparison,
    MatchField,
    MatchingConfig,
    MatchLevel,
    MatchReason,
    MatchResult,
)
from src.osap.domain.normalization import normalize_name
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.work_matcher import IWorkMatcher

# Authorities that identify a *work* (shared => safe coincidence).
_WORK_AUTHORITY_KINDS = {
    "wikidata",
    "musicbrainz_work",
    "musicbrainz-work",
    "imslp",
    "openscore",
    "omr",
    "rism",
    "iswc",
    "ismn",
}
# Authorities that identify a *person* (help the composer).
_PERSON_AUTHORITY_KINDS = {"viaf", "isni", "loc", "bnf"}

_AUTHORITY_ENUM: dict[str, Authority] = {
    "wikidata": Authority.WIKIDATA,
    "musicbrainz_work": Authority.MUSICBRAINZ_WORK,
    "musicbrainz-work": Authority.MUSICBRAINZ_WORK,
    "imslp": Authority.IMSLP,
    "omr": Authority.OMR,
    "openscore": Authority.OPENSCORE,
    "rism": Authority.RISM,
    "iswc": Authority.ISWC,
    "viaf": Authority.VIAF,
    "isni": Authority.ISNI,
    "loc": Authority.LOC,
    "bnf": Authority.BNF,
}

_TITLE_PARTIAL_SCORE = 0.6


class DefaultWorkMatcher(IWorkMatcher):
    """Pure, deterministic `IWorkMatcher` implementing the frozen contract.

    Compares canonicalized concepts, not strings. Weights, vetoes and safe-match
    rules live in `MatchingConfig` (policy), injected at construction.
    """

    def __init__(self, config: MatchingConfig) -> None:
        self._config = config

    def match(self, first: WorkDescriptor, second: WorkDescriptor) -> MatchResult:
        reasons: list[MatchReason] = []
        numerator = 0.0
        denominator = 0.0

        # Iterate the configured weights, so fields can be disabled without code.
        for field in self._config.weights:
            reason = self._compare_field(field, first, second)
            if reason is FieldComparison.SKIPPED:
                continue
            weight = self._config.weights[field]
            numerator += weight * reason.field_score
            denominator += weight
            reasons.append(reason)

        match_score = numerator / denominator if denominator > 0 else 0.0
        compared_fields = tuple(reason.field for reason in reasons)
        matched_fields = tuple(reason.field for reason in reasons if reason.field_score == 1.0)
        mismatched_fields = tuple(reason.field for reason in reasons if reason.field_score < 1.0)

        return MatchResult(
            level=self._level(match_score, reasons),
            match_score=match_score,
            compared_fields=compared_fields,
            matched_fields=matched_fields,
            mismatched_fields=mismatched_fields,
            reasons=tuple(reasons),
        )

    def _level(self, match_score: float, reasons: list[MatchReason]) -> MatchLevel:
        by_field = {reason.field: reason for reason in reasons}

        # Rule: a vetoed field that differs (both present) forces DIFFERENT.
        for field in self._config.vetoes:
            reason = by_field.get(field)
            if reason is not None and reason.field_score < 1.0:
                return MatchLevel.DIFFERENT

        # Rule: a safe match (both present, matched) forces SAME.
        for field in self._config.safe_match_fields:
            reason = by_field.get(field)
            if reason is not None and reason.field_score == 1.0:
                return MatchLevel.SAME

        if match_score >= self._config.same_threshold:
            return MatchLevel.SAME
        if match_score >= self._config.possible_threshold:
            return MatchLevel.POSSIBLE
        return MatchLevel.DIFFERENT

    @staticmethod
    def _compare_field(
        field: MatchField, first: WorkDescriptor, second: WorkDescriptor
    ) -> MatchReason | FieldComparison:
        left = _field_value(field, first)
        right = _field_value(field, second)
        if left is None or right is None:
            return FieldComparison.SKIPPED
        return MatchReason(
            field=field,
            field_score=_field_score(field, left, right),
            left=_display(left),
            right=_display(right),
        )


def _field_value(field: MatchField, work: WorkDescriptor) -> object | None:
    if field is MatchField.CATALOGUE:
        return _norm(work.catalogue_number)
    if field is MatchField.OPUS:
        return _norm(work.opus)
    if field is MatchField.COMPOSER:
        return _norm(work.composer)
    if field is MatchField.TITLE:
        return _norm(work.canonical_title or work.title)
    if field is MatchField.KEY:
        return _norm(work.key)
    if field is MatchField.MOVEMENT:
        return _movement_value(work)
    if field is MatchField.CREATION_YEAR:
        return str(work.creation_year) if work.creation_year is not None else None
    if field is MatchField.GENRES:
        return work.genres or None
    if field is MatchField.INSTRUMENTATION:
        combined = tuple(work.instrumentation) + tuple(work.voices)
        return combined or None
    if field is MatchField.WORK_AUTHORITY:
        return _authority_keys(work, _WORK_AUTHORITY_KINDS) or None
    if field is MatchField.PERSON_AUTHORITY:
        return _authority_keys(work, _PERSON_AUTHORITY_KINDS) or None
    assert_never(field)


def _field_score(field: MatchField, left: object, right: object) -> float:
    if field is MatchField.TITLE:
        if left == right:
            return 1.0
        return _TITLE_PARTIAL_SCORE if _contains(str(left), str(right)) else 0.0
    if field in (MatchField.GENRES, MatchField.INSTRUMENTATION):
        return 1.0 if _shares(left, right) else 0.0
    if field is MatchField.MOVEMENT:
        return 1.0 if _movement_equal(left, right) else 0.0
    if field in (MatchField.WORK_AUTHORITY, MatchField.PERSON_AUTHORITY):
        return 1.0 if _shares(left, right) else 0.0
    return 1.0 if left == right else 0.0


def _movement_value(work: WorkDescriptor) -> str | None:
    if work.movement:
        return _norm(work.movement)
    if work.movement_number is not None:
        return str(work.movement_number)
    return None


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_name(value)
    return normalized or None


def _authority_keys(work: WorkDescriptor, role: set[str]) -> frozenset[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for identifier in work.identifiers:
        kind = identifier.kind.lower().replace(" ", "_")
        if kind in role:
            keys.add((kind, identifier.value))
    return frozenset(keys)


def _contains(left: str, right: str) -> bool:
    return left in right or right in left


def _shares(left: object, right: object) -> bool:
    return bool(set(cast("Iterable[object]", left)) & set(cast("Iterable[object]", right)))


def _movement_equal(left: object, right: object) -> bool:
    a = str(left).strip().lower()
    b = str(right).strip().lower()
    return a == b or a.lstrip("0") == b.lstrip("0")


def _display(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in value)
    if isinstance(value, frozenset):
        return "; ".join(f"{kind}:{val}" for kind, val in sorted(value))
    return str(value)
