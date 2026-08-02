from abc import ABC, abstractmethod

from ..domain.pipeline_context import PipelineContext


class IPipelineStage(ABC):
    """A pluggable pipeline stage (lookup, dataset, download, omr, merge, ...)."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineContext:
        raise NotImplementedError
