from abc import ABC, abstractmethod

from ..domain.evidence import EvidenceItem


class IEvidenceContributor(ABC):
    """Something that produces evidence items (facts), never text."""

    @abstractmethod
    def to_evidence(self) -> tuple[EvidenceItem, ...]:
        raise NotImplementedError
