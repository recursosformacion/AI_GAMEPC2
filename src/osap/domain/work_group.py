"""WorkGroup: all normalized representations of a single work.

Domain-level value object (ADR-0035, D1): the canonical grouping concept lives in the
domain so neither ``domain/`` nor ``ports/`` depend on ``application/``. ``WorkGroup`` is
also re-exported from ``application/execution_plan`` for compatibility.
"""

from dataclasses import dataclass, field

from .candidate_representation import CandidateRepresentation
from .value_objects import ProviderId
from .work_descriptor import WorkDescriptor


@dataclass(frozen=True)
class WorkGroup:
    """All normalized representations of a single work, from any provider."""

    work: WorkDescriptor
    representations: tuple[CandidateRepresentation, ...] = field(default_factory=tuple)
    providers: tuple[ProviderId, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        """Canonical identity key (compat: legacy display grouping used `group.key`)."""
        return self.work.canonical_key or self.work.work_id.value

    @property
    def primary(self) -> CandidateRepresentation | None:
        """Best-preference representation (first of the ordered set), if any."""
        return self.representations[0] if self.representations else None
