"""Matcher: ¿fusiona o no?

Procedimiento de DECISIÓN POR REGLAS con prioridad sobre la identidad
normalizada (RepresentationIdentity). Es un consumidor del motor real
(src/osap): compara igualdades y emite un MergeDecision (score + evidencia).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.application.work_grouper import WorkGrouper
from src.osap.application.work_matcher import (
    MergeDecision,
    MergeVerdict,
    WorkMatcher,
)

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation

__all__ = ["WorkMatcher", "WorkGrouper", "MergeDecision", "MergeVerdict", "compare", "group"]


def compare(
    a: CandidateRepresentation, b: CandidateRepresentation, matcher: WorkMatcher | None = None
) -> MergeDecision:
    """¿Se fusionan dos representaciones? (reglas con prioridad + evidencia)."""
    return (matcher or WorkMatcher()).compare(a, b)


def group(
    reps: tuple[CandidateRepresentation, ...], matcher: WorkMatcher | None = None
) -> tuple[object, ...]:
    """Agrupa representaciones en obras (clusters)."""
    return WorkGrouper(matcher or WorkMatcher()).group(reps)
