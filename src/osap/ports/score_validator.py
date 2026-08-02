from abc import ABC, abstractmethod

from ..domain.acquisition_result import AcquisitionResult
from ..domain.score import Score


class IScoreValidator(ABC):
    """Turns an acquisition result into a validated Score with an assigned quality level."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def validate(self, result: AcquisitionResult) -> Score:
        raise NotImplementedError
