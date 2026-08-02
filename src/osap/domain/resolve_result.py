from dataclasses import dataclass, field

from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import Duration, ProviderId
from src.osap.domain.work_descriptor import WorkDescriptor


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
    local_path: str | None = None
    score_id: str | None = None
    downloaded: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
