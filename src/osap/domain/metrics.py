from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class MetricRecord:
    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
