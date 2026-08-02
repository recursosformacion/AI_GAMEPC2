from dataclasses import dataclass, field

from .musical_source import MusicalSource
from .output_format import OutputFormat
from .quality_level import QualityLevel
from .value_objects import Confidence, Duration, ProviderId


@dataclass(frozen=True)
class AcquisitionResult:
    provider_id: ProviderId
    source: MusicalSource
    confidence: Confidence
    processing_time: Duration
    format: OutputFormat
    quality_level: QualityLevel = QualityLevel.UNREADABLE
    warnings: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: dict[str, object] = field(default_factory=dict)
