from abc import ABC, abstractmethod

from ..domain.pipeline_context import PipelineContext
from .pipeline_stage import IPipelineStage


class IPipelineEngine(ABC):
    """Composes pipeline stages dynamically (add/remove without modifying it)."""

    @abstractmethod
    def add_stage(self, stage: IPipelineStage) -> None:
        raise NotImplementedError

    @abstractmethod
    def run(self, context: PipelineContext) -> PipelineContext:
        raise NotImplementedError
