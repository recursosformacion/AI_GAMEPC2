from src.osap.domain.knowledge_base_entry import KnowledgeBaseEntry
from src.osap.domain.value_objects import ProviderId
from src.osap.ports.knowledge_base import IKnowledgeBase


class InMemoryKnowledgeBase(IKnowledgeBase):
    def __init__(self) -> None:
        self._entries: dict[str, KnowledgeBaseEntry] = {}

    def store(self, entry: KnowledgeBaseEntry) -> None:
        raise NotImplementedError

    def find_by_signature(self, signature: str) -> KnowledgeBaseEntry | None:
        raise NotImplementedError

    def find_best_provider_for(self, signature: str) -> ProviderId | None:
        raise NotImplementedError
