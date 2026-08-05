from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..domain.ranking import RankingConfig, RankingContext, RankingResult

if TYPE_CHECKING:
    from ..application.execution_plan import WorkGroup


class IWorkRanker(ABC):
    """Ranks already-grouped works (`WorkGroup`) without changing their identity.

    Pure, deterministic, explainable, no AI, no I/O. Never modifies its inputs.
    """

    @abstractmethod
    def rank(
        self, works: tuple["WorkGroup", ...], context: RankingContext, config: RankingConfig
    ) -> RankingResult:
        raise NotImplementedError
