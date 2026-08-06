from abc import ABC, abstractmethod

from ..domain.knowledge import KnowledgeBase


class IKnowledgeMiner(ABC):
    """Analyzes a KnowledgeBase: aggregates observations into Facts and derives
    Suggestions. Deterministic and reproducible; never modifies the input."""

    @abstractmethod
    def mine(self, base: KnowledgeBase) -> KnowledgeBase:
        raise NotImplementedError
