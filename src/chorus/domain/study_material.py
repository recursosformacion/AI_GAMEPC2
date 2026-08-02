from dataclasses import dataclass, field
from typing import Any

from .material_type import MaterialType


@dataclass
class StudyMaterial:
    material_type: MaterialType
    content: Any
    voice: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.content is None:
            raise ValueError("StudyMaterial content cannot be None")
