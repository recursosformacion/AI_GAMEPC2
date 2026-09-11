from dataclasses import dataclass, field

from .candidate_representation import CandidateRepresentation
from .evidence import Evidence
from .resolve_request import ResolveRequest
from .value_objects import Duration, ProviderId
from .work_descriptor import WorkDescriptor


@dataclass(frozen=True)
class ResolveResult:
    """Outcome of a work resolution, explaining how and why it was chosen."""

    request: ResolveRequest
    selected_work: WorkDescriptor
    chosen: CandidateRepresentation | None
    ranking: tuple[CandidateRepresentation, ...]
    providers_used: tuple[ProviderId, ...]
    duration: Duration
    selection_reason: str | None = None
    evidence: Evidence | None = None
    local_path: str | None = None
    score_id: str | None = None
    downloaded: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
