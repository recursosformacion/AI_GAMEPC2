from dataclasses import dataclass, field

from .edition import Edition
from .output_format import OutputFormat
from .value_objects import ArrangementId


@dataclass(frozen=True)
class Arrangement:
    """A concrete arrangement (voices/instrumentation) of an Edition."""

    arrangement_id: ArrangementId
    edition: Edition
    arranger: str | None = None
    voices: tuple[str, ...] = field(default_factory=tuple)
    instrumentation: tuple[str, ...] = field(default_factory=tuple)
    format: OutputFormat = OutputFormat.SCORE
    metadata: dict[str, object] = field(default_factory=dict)
