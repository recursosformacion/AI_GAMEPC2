"""Backward-compatible facade over the scored matching pipeline.

The real grouping logic now lives in ``work_grouper`` (``WorkGrouper``) using
``work_grouping_matcher`` (``WorkGroupingMatcher`` + ``MergeDecision``). This module keeps the
pre-existing public API (``WorkMergeService``, ``WorkGroup``, ``_sort_key``) so
the rest of OSAP (engine, CLI, API) does not change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.application.work_grouper import WorkGroup, WorkGrouper, _sort_key

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation

__all__ = ["WorkMergeService", "WorkGroup", "_sort_key"]


class WorkMergeService:
    """Groups equivalent CandidateRepresentations into distinct works.

    Delegates to ``WorkGrouper`` + ``WorkGroupingMatcher`` (scored ``MergeDecision``).
    """

    def __init__(self) -> None:
        self._grouper = WorkGrouper()

    def group(self, candidates: tuple[CandidateRepresentation, ...]) -> tuple[WorkGroup, ...]:
        return self._grouper.group(candidates)
