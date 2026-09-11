from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..domain.ranking import RankingContext, RankingPolicy, RankingResult

if TYPE_CHECKING:
    from ..domain.work_group import WorkGroup


class IWorkRanker(ABC):
    """Ranks already-grouped works (`WorkGroup`) without changing their identity.

    Pure, deterministic, explainable, no AI, no I/O. Never modifies its inputs.
    """

    @abstractmethod
    def rank(
        self, works: tuple["WorkGroup", ...], context: RankingContext, policy: RankingPolicy
    ) -> RankingResult:
        raise NotImplementedError
