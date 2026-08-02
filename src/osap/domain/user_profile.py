from dataclasses import dataclass, field

from .output_format import OutputFormat
from .quality_level import QualityLevel
from .value_objects import LibraryId, ProviderId


@dataclass(frozen=True)
class UserProfile:
    """User preferences used by the RankingEngine and the pipeline."""

    user_id: str
    language: str | None = None
    preferred_providers: tuple[ProviderId, ...] = field(default_factory=tuple)
    preferred_formats: tuple[OutputFormat, ...] = field(default_factory=tuple)
    min_quality: QualityLevel = QualityLevel.PARTIAL_STRUCTURE
    voice_types: tuple[str, ...] = field(default_factory=tuple)
    favorite_libraries: tuple[LibraryId, ...] = field(default_factory=tuple)
