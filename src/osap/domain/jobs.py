"""V2.2.c Jobs — domain types.

A Job is an executable unit of work that only orchestrates existing processes. It
never contains business rules. These types model the *contract* of a Job, fully
separated from any scheduler (CLI, API, cron, Celery, APScheduler, workers...).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobTrigger(Enum):
    SCHEDULE = "schedule"
    API = "api"
    CLI = "cli"
    TEST = "test"


class JobEventType(Enum):
    STARTED = "started"
    PROGRESS = "progress"
    FINISHED = "finished"
    FAILED = "failed"


class JobErrorCode(Enum):
    PROCESSING = "processing"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class JobOption:
    """A single, typed execution option (per-job, never a dynamic dict)."""

    name: str
    value: object


@dataclass(frozen=True)
class JobContext:
    """Execution information only. Never carries business rules."""

    execution_id: str
    started_at: datetime
    triggered_by: JobTrigger
    dry_run: bool
    options: tuple[JobOption, ...] = ()


@dataclass(frozen=True)
class JobError:
    """A structured, typed error. Not an `Exception`, not a free string."""

    code: JobErrorCode
    field: str | None = None
    context: tuple[object, ...] = ()


@dataclass(frozen=True)
class JobResult:
    """Typed outcome of a single execution, fully deterministic."""

    status: JobStatus
    duration: timedelta
    processed_count: int
    skipped_count: int
    failed_count: int
    errors: tuple[JobError, ...] = ()


@dataclass(frozen=True)
class JobEvent:
    """A typed event produced by a Job (observability; never direct logging)."""

    type: JobEventType
    execution_id: str
    timestamp: datetime
    payload: object = None
