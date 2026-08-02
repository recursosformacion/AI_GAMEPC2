from abc import ABC, abstractmethod

from ..domain.job import Job, JobState, JobSubmission
from ..domain.value_objects import JobId


class IJobRunner(ABC):
    """Runs asynchronous jobs (download, OMR, merge, generation)."""

    @abstractmethod
    def submit(self, submission: JobSubmission) -> Job:
        raise NotImplementedError

    @abstractmethod
    def cancel(self, job_id: JobId) -> None:
        raise NotImplementedError

    @abstractmethod
    def status(self, job_id: JobId) -> JobState:
        raise NotImplementedError

    @abstractmethod
    def get(self, job_id: JobId) -> Job | None:
        raise NotImplementedError
