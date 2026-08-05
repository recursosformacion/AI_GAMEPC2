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
