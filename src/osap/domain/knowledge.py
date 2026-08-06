"""V2.2.d Knowledge Mining — domain types.

Knowledge Mining never modifies the system's knowledge; it only transforms repeated
observations into verifiable suggestions. Everything here is an immutable Value Object.
"""

from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import Enum


class KnowledgeSource(Enum):
    CANONICALIZER = "canonicalizer"
    MATCHER = "matcher"
    RANKING = "ranking"
    MERGE = "merge"
    EVIDENCE = "evidence"


class KnowledgeFactType(Enum):
    ALIAS = "alias"
    AUTHORITY = "authority"
    FREQUENCY = "frequency"
    DISCREPANCY = "discrepancy"
    PATTERN = "pattern"


class KnowledgeSuggestionType(Enum):
    ADD_ALIAS = "add_alias"
    ADJUST_AUTHORITY = "adjust_authority"
    RECORD_ANOMALY = "record_anomaly"


@dataclass(frozen=True)
class KnowledgeObservation:
    """An immutable fact observed during a single execution.

    Not a summary, not a statistic: a single observed fact. Belongs to exactly one
    execution (`execution_id`).
    """

    execution_id: str
    source: KnowledgeSource
    field: str
    value: str
    provider: str | None = None


@dataclass(frozen=True)
class KnowledgeFact:
    """A derived fact. Never emitted directly by a component; born from the Miner.

    Always reproducible, verifiable and traceable (references source observations).
    """

    fact_type: KnowledgeFactType
    field: str
    value: str
    count: int
    sources: tuple[KnowledgeSource, ...] = dc_field(default_factory=tuple)
    observation_ids: tuple[str, ...] = dc_field(default_factory=tuple)

    @property
    def signature(self) -> str:
        return f"{self.fact_type.value}:{self.field}:{self.value}"


@dataclass(frozen=True)
class KnowledgeSuggestion:
    """A verifiable proposal. Never constitutes system knowledge; proposes an evolution.

    Reproducible: re-running the Miner on the same KnowledgeBase yields the same
    suggestions.
    """

    suggestion_type: KnowledgeSuggestionType
    field: str
    source_value: str
    target_value: str
    reason: str
    fact_ids: tuple[str, ...] = dc_field(default_factory=tuple)


@dataclass(frozen=True)
class KnowledgeBase:
    """The complete state of the knowledge learned by OSAP at a given instant."""

    observations: tuple[KnowledgeObservation, ...] = dc_field(default_factory=tuple)
    facts: tuple[KnowledgeFact, ...] = dc_field(default_factory=tuple)
    suggestions: tuple[KnowledgeSuggestion, ...] = dc_field(default_factory=tuple)
