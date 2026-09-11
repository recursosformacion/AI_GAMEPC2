"""PlatformApi: mixin de jobs (F5.4)."""

from datetime import UTC, datetime

from src.osap.api.contracts import (
    JobResponse,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform.core import PlatformApiCore
from src.osap.application.jobs import DefaultJob
from src.osap.domain.jobs import JobContext, JobTrigger

VERSION = "3.1"



















class JobsMixin(PlatformApiCore):
    def create_job(self, job_type: str) -> JobResponse:
        self._job_counter += 1
        job_id = f"job-{self._job_counter}"
        context = JobContext(
            execution_id=job_id,
            started_at=datetime.now(UTC),
            triggered_by=JobTrigger.API,
            dry_run=False,
        )
        result = DefaultJob().run(context)
        response = JobResponse(job_id=job_id, type=job_type, state=result.status.value, progress=100, result={})
        self._jobs[job_id] = response
        return response

    def list_jobs(self) -> list[JobResponse]:
        return sorted(self._jobs.values(), key=lambda job: job.job_id)

    def get_job(self, job_id: str) -> JobResponse | None:
        return self._jobs.get(job_id)

    # --- providers ----------------------------------------------------------

