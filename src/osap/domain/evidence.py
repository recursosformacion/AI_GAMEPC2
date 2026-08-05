from dataclasses import dataclass, field
from enum import Enum

from .value_objects import ProviderId


class EvidenceReasonKind(Enum):
    CONFIDENCE = "confidence"
    FORMAT = "format"
    PUBLIC_DOMAIN = "public_domain"
    QUALITY = "quality"
    COMPLETENESS = "completeness"
    CHECKSUM = "checksum"


@dataclass(frozen=True)
class EvidenceReason:
    """A single, structured reason why a representation was (not) favored."""

    kind: EvidenceReasonKind
    satisfied: bool
    detail: str = ""


@dataclass(frozen=True)
class EvidenceMetrics:
    """Normalized metrics of the chosen representation (0..1)."""

    confidence: float
    quality: float
    completeness: float


@dataclass(frozen=True)
class Evidence:
    """Structured explanation of why OSAP chose a representation.

    Fully structured (not natural language): a later layer may render it to text.
    """

    provider_id: ProviderId
    reasons: tuple[EvidenceReason, ...] = field(default_factory=tuple)
    metrics: EvidenceMetrics = field(default_factory=lambda: EvidenceMetrics(0.0, 0.0, 0.0))
    checksum: str | None = None
    ranking_score: float = 0.0


class EvidenceSource(Enum):
    MATCHER = "matcher"
    RANKER = "ranker"
    SELECTION = "selection"


class EvidenceCode(Enum):
    # matcher
    CATALOGUE_MATCH = "catalogue_match"
    COMPOSER_MATCH = "composer_match"
    TITLE_MATCH = "title_match"
    WORK_AUTHORITY_MATCH = "work_authority_match"
    KEY_MATCH = "key_match"
    # ranker
    RELEVANCE = "relevance"
    QUALITY_CONFIDENCE = "quality_confidence"
    QUALITY_COMPLETENESS = "quality_completeness"
    PREFERRED_FORMAT = "preferred_format"
    PREFERRED_LICENSE = "preferred_license"
    COVERAGE = "coverage"
    # selection
    SELECTED_REPRESENTATION = "selected_representation"


class EvidenceStrength(Enum):
    CRITICAL = "critical"
    STRONG = "strong"
    NORMAL = "normal"
    WEAK = "weak"


@dataclass(frozen=True)
class EvidenceField:
    name: str
    value: object


@dataclass(frozen=True)
class EvidenceItem:
    source: EvidenceSource
    code: EvidenceCode
    score: float
    strength: EvidenceStrength = EvidenceStrength.NORMAL
    fields: tuple[EvidenceField, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceSummary:
    matcher_score: float
    ranking_score: float
    selection_score: float
    overall_score: float


@dataclass(frozen=True)
class EvidenceResult:
    items: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    summary: EvidenceSummary = field(default_factory=lambda: EvidenceSummary(0.0, 0.0, 0.0, 0.0))
    overall_score: float = 0.0
