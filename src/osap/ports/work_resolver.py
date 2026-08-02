from abc import ABC, abstractmethod

from ..domain.resolve_request import ResolveRequest
from ..domain.work_descriptor import WorkDescriptor


class IWorkResolver(ABC):
    """Resolves and normalizes the identity of a work, independently of data origin."""

    @abstractmethod
    def resolve(self, request: ResolveRequest) -> WorkDescriptor:
        raise NotImplementedError

    @abstractmethod
    def is_same_work(self, first: WorkDescriptor, second: WorkDescriptor) -> bool:
        raise NotImplementedError
