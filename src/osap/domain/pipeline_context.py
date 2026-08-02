from dataclasses import dataclass, field

from .candidate_representation import CandidateRepresentation
from .resolve_request import ResolveRequest
from .resolve_result import ResolveResult


@dataclass(frozen=True)
class PipelineContext:
    """Immutable-ish context flowing through pipeline stages."""

    request: ResolveRequest | None = None
    candidates: tuple[CandidateRepresentation, ...] = field(default_factory=tuple)
    result: ResolveResult | None = None
    logs: tuple[str, ...] = field(default_factory=tuple)
    data: dict[str, object] = field(default_factory=dict)

    def with_data(self, **kwargs: object) -> "PipelineContext":
        merged = dict(self.data)
        merged.update(kwargs)
        return PipelineContext(
            request=self.request,
            candidates=self.candidates,
            result=self.result,
            logs=self.logs,
            data=merged,
        )

    def with_result(self, result: ResolveResult) -> "PipelineContext":
        return PipelineContext(
            request=self.request,
            candidates=self.candidates,
            result=result,
            logs=self.logs + (f"result: {result.score_id or result.selection_reason}",),
            data=self.data,
        )
