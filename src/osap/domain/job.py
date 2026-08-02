from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from .value_objects import JobId


class JobState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobResult:
    success: bool
    payload: dict[str, object] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Job:
    """An asynchronous, long-running operation (download, OMR, merge, ...)."""

    job_id: JobId
    type: str
    state: JobState = JobState.PENDING
    progress: int = 0
    logs: tuple[str, ...] = field(default_factory=tuple)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: JobResult | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.progress <= 100:
            raise ValueError("progress must be in [0, 100]")


@dataclass(frozen=True)
class JobSubmission:
    job_id: JobId
    type: str
    params: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
