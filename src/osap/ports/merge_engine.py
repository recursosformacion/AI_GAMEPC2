from abc import ABC, abstractmethod

from ..domain.acquisition_result import AcquisitionResult
from ..domain.score import Score


class IMergeEngine(ABC):
    """Combines several representations/sources into a new Score.

    Architecture only for now; complex algorithms come later.
    """

    @abstractmethod
    def merge(self, sources: tuple[AcquisitionResult, ...]) -> Score:
        raise NotImplementedError
