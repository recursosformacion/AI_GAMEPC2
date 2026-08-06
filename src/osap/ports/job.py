from abc import ABC, abstractmethod

from ..domain.jobs import JobContext, JobResult


class IJob(ABC):
    """A unit of work that only orchestrates existing processes.

    Pure relative to the domain, idempotent when possible, cancelable and observable.
    It never contains business rules and never knows how it is executed (no scheduler).
    """

    @abstractmethod
    def run(self, context: JobContext) -> JobResult:
        raise NotImplementedError
