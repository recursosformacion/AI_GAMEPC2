from dataclasses import dataclass, field

from .output_format import OutputFormat
from .value_objects import SourceId


@dataclass(frozen=True)
class MusicalSource:
    source_id: SourceId
    content: object
    format: OutputFormat
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.content is None:
            raise ValueError("MusicalSource content cannot be None")
