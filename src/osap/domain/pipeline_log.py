from dataclasses import dataclass, field
from datetime import UTC, datetime

from .output_format import OutputFormat
from .quality_level import QualityLevel
from .strategy_kind import StrategyKind
from .value_objects import Duration, ProviderId, RequestId


@dataclass(frozen=True)
class PipelineStep:
    step_name: str
    provider_id: ProviderId | None = None
    result: object | None = None
    success: bool = False
    strategy_kind: StrategyKind | None = None
    duration: Duration | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.step_name:
            raise ValueError("step_name cannot be empty")


@dataclass(frozen=True)
class PipelineLog:
    request_id: RequestId
    steps: tuple[PipelineStep, ...] = field(default_factory=tuple)
    selected_provider_id: ProviderId | None = None
    final_quality_level: QualityLevel = QualityLevel.UNREADABLE
    output_format: OutputFormat = OutputFormat.SCORE
    human_intervention: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
