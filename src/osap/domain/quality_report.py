from dataclasses import dataclass, field
from enum import Enum

from .quality_level import QualityLevel


class QualityDimension(Enum):
    STRUCTURE = "structure"
    NOTATION = "notation"
    LYRICS = "lyrics"
    HARMONY = "harmony"
    VOICES = "voices"
    METADATA = "metadata"
    ATTACHMENTS = "attachments"


@dataclass(frozen=True)
class QualityReport:
    """Multi-dimensional quality assessment.

    Each dimension scores independently in [0, 1]. The overall `QualityLevel`
    is derived from the dimension scores, so Chorus can decide which materials
    a score supports.
    """

    dimensions: dict[QualityDimension, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for dimension, score in self.dimensions.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"{dimension.value} score must be in [0, 1]")

    def score(self, dimension: QualityDimension) -> float:
        return self.dimensions.get(dimension, 0.0)

    def overall(self) -> float:
        if not self.dimensions:
            return 0.0
        return sum(self.dimensions.values()) / len(self.dimensions)

    def quality_level(self) -> QualityLevel:
        overall = self.overall()
        if overall >= 0.9:
            return QualityLevel.HUMAN_VALIDATED
        if overall >= 0.7:
            return QualityLevel.FULL_NOTATION
        if overall >= 0.5:
            return QualityLevel.BASIC_MELODY
        if overall >= 0.25:
            return QualityLevel.PARTIAL_STRUCTURE
        return QualityLevel.UNREADABLE
