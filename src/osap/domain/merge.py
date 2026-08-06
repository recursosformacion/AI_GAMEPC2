from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import Enum

from .evidence import EvidenceItem


class MergeCriterion(Enum):
    SOURCE_AUTHORITY = "source_authority"
    FIELD_COMPLETENESS = "field_completeness"
    REPRESENTATION_CONFIDENCE = "representation_confidence"
    MAJORITY = "majority"
    NEWEST = "newest"
    MANUAL_PRIORITY = "manual_priority"


class MergeConflictType(Enum):
    IDENTITY_CONFLICT = "identity_conflict"
    VALUE_CONFLICT = "value_conflict"
    MISSING_DATA = "missing_data"
    AUTHORITY_CONFLICT = "authority_conflict"
    FORMAT_CONFLICT = "format_conflict"


@dataclass(frozen=True)
class MergeConflict:
    """A discrepancy Merge did not resolve silently."""

    field: str
    conflict_type: MergeConflictType
    values: tuple[object, ...] = dc_field(default_factory=tuple)
    sources: tuple[str, ...] = dc_field(default_factory=tuple)


@dataclass(frozen=True)
class MergeProvenance:
    """Why a field value was chosen (traceability)."""

    field: str
    value: object
    source: str
    strategy: MergeCriterion
    confidence: float


@dataclass(frozen=True)
class MergedWorkDescriptor:
    """Consolidated knowledge of a work. Not a `WorkDescriptor` (a representation)."""

    title: str
    composer: str | None = None
    catalogue_number: str | None = None
    opus: str | None = None
    subtitle: str | None = None
    language: str | None = None
    key: str | None = None
    creation_year: int | None = None
    genres: tuple[str, ...] = dc_field(default_factory=tuple)
    instrumentation: tuple[str, ...] = dc_field(default_factory=tuple)
    voices: tuple[str, ...] = dc_field(default_factory=tuple)
    aliases: tuple[str, ...] = dc_field(default_factory=tuple)


@dataclass(frozen=True)
class MergePolicy:
    """Policy: which criteria win when values differ (not part of the contract)."""

    enabled_criteria: tuple[MergeCriterion, ...] = (MergeCriterion.REPRESENTATION_CONFIDENCE,)
    weights: dict[MergeCriterion, float] = dc_field(default_factory=dict)


@dataclass(frozen=True)
class MergeResult:
    merged_descriptor: MergedWorkDescriptor
    provenance: tuple[MergeProvenance, ...] = dc_field(default_factory=tuple)
    conflicts: tuple[MergeConflict, ...] = dc_field(default_factory=tuple)
    evidence: tuple[EvidenceItem, ...] = dc_field(default_factory=tuple)
