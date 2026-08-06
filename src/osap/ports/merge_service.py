from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..domain.merge import MergePolicy, MergeResult

if TYPE_CHECKING:
    from ..application.execution_plan import WorkGroup


class IMergeService(ABC):
    """Consolidates the descriptive knowledge of a `WorkGroup`.

    It never decides identity, never creates/breaks `WorkGroup`s and never re-runs
    the Matcher. Pure, deterministic, immutable, order-independent, no AI, no text.
    """

    @abstractmethod
    def merge(self, group: "WorkGroup", policy: MergePolicy) -> MergeResult:
        raise NotImplementedError
