from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Event:
    """A domain event published on the EventBus (progress, monitoring, UI)."""

    event_type: str
    aggregate_id: str | None = None
    payload: dict[str, object] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
