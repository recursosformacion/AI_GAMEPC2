from abc import ABC, abstractmethod

from ..domain.candidate_representation import CandidateRepresentation
from ..domain.work_descriptor import WorkDescriptor


class IDuplicateResolver(ABC):
    """Determines whether two representations correspond to the same work.

    Uses title, composer, duration, instrumentation, measures, key and hashes.
    Never depends on the provider.
    """

    @abstractmethod
    def is_duplicate(self, first: CandidateRepresentation, second: CandidateRepresentation) -> bool:
        raise NotImplementedError

    @abstractmethod
    def canonical(self, candidate: CandidateRepresentation) -> WorkDescriptor:
        raise NotImplementedError
