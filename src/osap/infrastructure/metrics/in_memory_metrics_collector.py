from src.osap.domain.metrics import MetricRecord
from src.osap.ports.metrics import IMetricsCollector


class InMemoryMetricsCollector(IMetricsCollector):
    def __init__(self) -> None:
        self._records: list[MetricRecord] = []

    def record(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        self._records.append(MetricRecord(name=name, value=value, tags=tags or {}))

    def snapshot(self) -> tuple[MetricRecord, ...]:
        return tuple(self._records)
