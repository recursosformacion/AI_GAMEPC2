from dataclasses import dataclass, field
from enum import Enum


class MatchField(Enum):
    CATALOGUE = "catalogue"
    OPUS = "opus"
    COMPOSER = "composer"
    TITLE = "title"
    KEY = "key"
    MOVEMENT = "movement"
    CREATION_YEAR = "creation_year"
    GENRES = "genres"
    INSTRUMENTATION = "instrumentation"
    WORK_AUTHORITY = "work_authority"
    PERSON_AUTHORITY = "person_authority"


class MatchLevel(Enum):
    SAME = "same"
    POSSIBLE = "possible"
    DIFFERENT = "different"


class FieldComparison(Enum):
    """Per-field outcome marker: a field was skipped (not compared)."""

    SKIPPED = "skipped"


class Authority(Enum):
    WIKIDATA = "wikidata"
    MUSICBRAINZ_WORK = "musicbrainz_work"
    IMSLP = "imslp"
    OMR = "omr"
    OPENSCORE = "openscore"
    RISM = "rism"
    ISWC = "iswc"
    VIAF = "viaf"
    ISNI = "isni"
    LOC = "loc"
    BNF = "bnf"
    UNKNOWN = "unknown"
    CUSTOM = "custom"


@dataclass(frozen=True)
class AuthorityIdentifier:
    authority: Authority
    value: str


@dataclass(frozen=True)
class MatchReason:
    field: MatchField
    field_score: float  # per-field score in [0, 1] (e.g. title partial = 0.6)
    left: str | None = None
    right: str | None = None


@dataclass(frozen=True)
class MatchResult:
    level: MatchLevel
    match_score: float
    compared_fields: tuple[MatchField, ...] = field(default_factory=tuple)
    matched_fields: tuple[MatchField, ...] = field(default_factory=tuple)
    mismatched_fields: tuple[MatchField, ...] = field(default_factory=tuple)
    reasons: tuple[MatchReason, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MatchingConfig:
    """Policy for how the matcher scores a match (weights and rules live here, not in the contract)."""

    same_threshold: float = 0.70
    possible_threshold: float = 0.40
    weights: dict[MatchField, float] = field(
        default_factory=lambda: {
            MatchField.CATALOGUE: 0.35,
            MatchField.OPUS: 0.20,
            MatchField.COMPOSER: 0.30,
            MatchField.TITLE: 0.25,
            MatchField.KEY: 0.05,
            MatchField.MOVEMENT: 0.05,
            MatchField.CREATION_YEAR: 0.05,
            MatchField.GENRES: 0.03,
            MatchField.INSTRUMENTATION: 0.03,
            MatchField.WORK_AUTHORITY: 1.0,
            MatchField.PERSON_AUTHORITY: 0.10,
        }
    )
    # Fields that force DIFFERENT when present in both sides but differing
    # (e.g. a contradictory catalogue number is decisive).
    vetoes: tuple[MatchField, ...] = (MatchField.CATALOGUE,)
    # Fields that force SAME when present in both sides and matched
    # (safe coincidence, e.g. a shared authoritative work identifier).
    safe_match_fields: tuple[MatchField, ...] = (MatchField.WORK_AUTHORITY,)
