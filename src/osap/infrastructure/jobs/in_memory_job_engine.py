import threading
from collections.abc import Callable
from datetime import UTC, datetime

from src.osap.domain.event import Event
from src.osap.domain.job import Job, JobResult, JobState, JobSubmission
from src.osap.domain.value_objects import JobId
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.ports.job_runner import IJobRunner

JobHandler = Callable[[JobSubmission], None]


class InMemoryJobEngine(IJobRunner):
    """Runs jobs asynchronously on a background thread pool.

    Long-running operations never block the caller/UI. Job state transitions
    (pending -> running -> completed/failed/cancelled) and events are exposed
    for a future REST/React frontend.
    """

    def __init__(self, event_bus: InMemoryEventBus) -> None:
        self._event_bus = event_bus
        self._jobs: dict[JobId, Job] = {}
        self._handlers: dict[str, JobHandler] = {}
        self._cancel: set[JobId] = set()

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def submit(self, submission: JobSubmission) -> Job:
        job = Job(job_id=submission.job_id, type=submission.type, state=JobState.PENDING)
        self._jobs[job.job_id] = job
        self._publish("JobSubmitted", job.job_id.value)
        thread = threading.Thread(target=self._run, args=(submission,), daemon=True)
        thread.start()
        return job

    def cancel(self, job_id: JobId) -> None:
        self._cancel.add(job_id)

    def status(self, job_id: JobId) -> JobState:
        return self._require(job_id).state

    def get(self, job_id: JobId) -> Job | None:
        return self._jobs.get(job_id)

    def jobs(self) -> tuple[Job, ...]:
        return tuple(self._jobs.values())

    def _run(self, submission: JobSubmission) -> None:
        job = self._jobs[submission.job_id]
        self._jobs[job.job_id] = self._transition(job, state=JobState.RUNNING, started_at=datetime.now(UTC))
        self._publish("JobStarted", job.job_id.value)
        handler = self._handlers.get(job.type)
        if handler is None:
            self._finish(job, JobResult(False, error=f"no handler for {job.type}"), JobState.FAILED)
            return
        try:
            handler(submission)
        except Exception as exc:  # noqa: BLE001
            self._finish(job, JobResult(False, error=str(exc)), JobState.FAILED)
            return
        if job.job_id in self._cancel:
            self._finish(job, JobResult(False, error="cancelled"), JobState.CANCELLED)
            return
        self._finish(job, JobResult(True), JobState.COMPLETED)

    def _finish(self, job: Job, result: JobResult, state: JobState) -> None:
        self._jobs[job.job_id] = self._transition(job, state=state, result=result, finished_at=datetime.now(UTC))
        self._publish(f"Job{state.value.capitalize()}", job.job_id.value)

    @staticmethod
    def _transition(
        job: Job,
        *,
        state: JobState,
        result: JobResult | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> Job:
        return Job(
            job_id=job.job_id,
            type=job.type,
            state=state,
            progress=job.progress,
            logs=job.logs,
            started_at=started_at if started_at is not None else job.started_at,
            finished_at=finished_at if finished_at is not None else job.finished_at,
            result=result if result is not None else job.result,
        )

    def _require(self, job_id: JobId) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"unknown job: {job_id.value}")
        return job

    def _publish(self, event_type: str, aggregate_id: str) -> None:
        self._event_bus.publish(Event(event_type=event_type, aggregate_id=aggregate_id))
