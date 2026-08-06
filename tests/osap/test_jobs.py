from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from src.osap.application.jobs import DefaultJob
from src.osap.domain.jobs import (
    JobContext,
    JobError,
    JobErrorCode,
    JobEvent,
    JobEventType,
    JobResult,
    JobStatus,
    JobTrigger,
)
from src.osap.ports.job import IJob


def _context(execution_id: str = "exec-1") -> JobContext:
    return JobContext(
        execution_id=execution_id,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        triggered_by=JobTrigger.CLI,
        dry_run=False,
    )


def _result() -> JobResult:
    return JobResult(
        status=JobStatus.COMPLETED,
        duration=timedelta(0),
        processed_count=0,
        skipped_count=0,
        failed_count=0,
        errors=(),
    )


def test_job_status_is_enum() -> None:
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_job_result_is_immutable() -> None:
    result = _result()
    with pytest.raises(FrozenInstanceError):
        result.processed_count = 1  # type: ignore[misc]


def test_job_context_is_immutable() -> None:
    context = _context()
    with pytest.raises(FrozenInstanceError):
        context.execution_id = "other"  # type: ignore[misc]


def test_job_event_is_immutable_and_typed() -> None:
    event = JobEvent(JobEventType.STARTED, "exec-1", datetime(2026, 1, 1, tzinfo=UTC))
    assert event.type is JobEventType.STARTED
    with pytest.raises(FrozenInstanceError):
        event.execution_id = "other"  # type: ignore[misc]


def test_job_error_is_typed() -> None:
    error = JobError(code=JobErrorCode.VALIDATION, field="dry_run")
    assert error.code is JobErrorCode.VALIDATION
    assert error.field == "dry_run"
    assert error.context == ()


def test_default_job_is_an_i_job() -> None:
    assert isinstance(DefaultJob(), IJob)


def test_run_is_deterministic() -> None:
    job = DefaultJob()
    assert job.run(_context("a")) == job.run(_context("a"))


def test_equality_between_executions() -> None:
    job = DefaultJob()
    assert job.run(_context("a")) == job.run(_context("b"))


def test_idempotent_repeated_runs() -> None:
    job = DefaultJob()
    first = job.run(_context())
    for _ in range(3):
        assert job.run(_context()) == first


def test_events_generated() -> None:
    received: list[JobEvent] = []
    job = DefaultJob(on_event=received.append)
    result = job.run(_context())
    assert result.status is JobStatus.COMPLETED
    assert [e.type for e in received] == [JobEventType.STARTED, JobEventType.FINISHED]
    assert all(e.execution_id == "exec-1" for e in received)


def test_dry_run_yields_same_contract_result() -> None:
    dry = _context()
    dry = JobContext(
        execution_id=dry.execution_id,
        started_at=dry.started_at,
        triggered_by=dry.triggered_by,
        dry_run=True,
    )
    assert DefaultJob().run(dry) == DefaultJob().run(_context())
