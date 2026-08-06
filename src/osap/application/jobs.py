from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from src.osap.domain.jobs import JobContext, JobEvent, JobEventType, JobResult, JobStatus
from src.osap.ports.job import IJob


class DefaultJob(IJob):
    """Minimal reference implementation of the Job contract (V2.2.c).

    A deterministic no-op: it emits STARTED and FINISHED events and returns a
    completed result with zero counts. It contains no business rules and serves
    only as an example of the contract. Idempotent: re-running yields equal results.
    """

    def __init__(self, on_event: Callable[[JobEvent], None] | None = None) -> None:
        self._on_event = on_event

    def run(self, context: JobContext) -> JobResult:
        self._emit(JobEvent(JobEventType.STARTED, context.execution_id, datetime.now(UTC)))
        result = JobResult(
            status=JobStatus.COMPLETED,
            duration=timedelta(0),
            processed_count=0,
            skipped_count=0,
            failed_count=0,
            errors=(),
        )
        self._emit(JobEvent(JobEventType.FINISHED, context.execution_id, datetime.now(UTC)))
        return result

    def _emit(self, event: JobEvent) -> None:
        if self._on_event is not None:
            self._on_event(event)
