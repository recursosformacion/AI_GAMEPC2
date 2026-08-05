from abc import ABC, abstractmethod

from ..domain.matching import MatchResult
from ..domain.work_descriptor import WorkDescriptor


class IWorkMatcher(ABC):
    """Compares two canonicalized `WorkDescriptor` and returns a `MatchResult`.

    Pure, deterministic, explainable, no AI, no I/O. Never modifies its inputs.
    """

    @abstractmethod
    def match(self, first: WorkDescriptor, second: WorkDescriptor) -> MatchResult:
        raise NotImplementedError
