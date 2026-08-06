from abc import ABC, abstractmethod

from ..domain.knowledge import KnowledgeBase, KnowledgeObservation


class IKnowledgeCollector(ABC):
    """Collects and normalizes observations into a KnowledgeBase. It does not think."""

    @abstractmethod
    def collect(self, observations: tuple[KnowledgeObservation, ...]) -> KnowledgeBase:
        raise NotImplementedError
