from abc import ABC, abstractmethod

from ..domain.metrics import MetricRecord


class IMetricsCollector(ABC):
    """Records timing/success/quality metrics independently of the pipeline."""

    @abstractmethod
    def record(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def snapshot(self) -> tuple[MetricRecord, ...]:
        raise NotImplementedError
