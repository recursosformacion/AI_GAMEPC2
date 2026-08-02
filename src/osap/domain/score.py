from dataclasses import dataclass, field

from .quality_level import QualityLevel
from .value_objects import ScoreId


@dataclass(frozen=True)
class Score:
    score_id: ScoreId
    content: object
    title: str | None = None
    composer: str | None = None
    quality_level: QualityLevel = QualityLevel.UNREADABLE
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.content is None:
            raise ValueError("Score content cannot be None")
