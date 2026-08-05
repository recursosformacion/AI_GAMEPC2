from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..domain.evidence import EvidenceResult

if TYPE_CHECKING:
    from .evidence_contributor import IEvidenceContributor


class IEvidenceCollector(ABC):
    """Collects evidence from contributors into a single `EvidenceResult`.

    It only knows evidence (`IEvidenceContributor`), never `MatchResult`,
    `RankingResult` nor `SelectionResult`. Pure, deterministic, no AI, no text.
    """

    @abstractmethod
    def collect(self, contributors: tuple["IEvidenceContributor", ...]) -> EvidenceResult:
        raise NotImplementedError
