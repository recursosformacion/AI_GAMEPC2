from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any


@dataclass
class DomainEvent:
    event_type: str
    payload: dict[str, Any]
    occurred_at: str = ""

    def __post_init__(self) -> None:
        if not self.occurred_at:
            object.__setattr__(self, "occurred_at", datetime.now(UTC).isoformat())
