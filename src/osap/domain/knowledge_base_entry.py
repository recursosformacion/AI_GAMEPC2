from dataclasses import dataclass, field
from datetime import UTC, datetime

from .output_format import OutputFormat
from .quality_level import QualityLevel
from .strategy_kind import StrategyKind
from .value_objects import Duration, ProviderId


@dataclass(frozen=True)
class KnowledgeBaseEntry:
    request_signature: str
    chosen_strategy: StrategyKind
    providers_used: tuple[ProviderId, ...]
    quality_level: QualityLevel
    processing_time: Duration
    output_format: OutputFormat
    library_id: str | None = None
    successful: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.request_signature:
            raise ValueError("request_signature cannot be empty")
