from dataclasses import dataclass

from .candidate_representation import CandidateRepresentation


@dataclass(frozen=True)
class ScoreRanking:
    """An explainable ranking result for a single candidate.

    Each criterion is scored independently so the user (and Chorus) can
    understand why a particular representation was chosen. No magic numbers.
    """

    candidate: CandidateRepresentation
    total: float
    details: dict[str, float]
    reason: str = ""

    def __post_init__(self) -> None:
        if self.total < 0:
            raise ValueError("total must be non-negative")
