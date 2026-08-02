from abc import ABC, abstractmethod

from ..domain.knowledge_base_entry import KnowledgeBaseEntry
from ..domain.value_objects import ProviderId


class IKnowledgeBase(ABC):
    """Records resolved experiences to improve future decisions."""

    @abstractmethod
    def store(self, entry: KnowledgeBaseEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_by_signature(self, signature: str) -> KnowledgeBaseEntry | None:
        raise NotImplementedError

    @abstractmethod
    def find_best_provider_for(self, signature: str) -> ProviderId | None:
        raise NotImplementedError
