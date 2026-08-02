from src.osap.domain.dataset_descriptor import DatasetDescriptor
from src.osap.domain.dataset_status import DatasetStatus
from src.osap.domain.value_objects import DatasetId
from src.osap.infrastructure.datasets.dataset_registry import IDatasetRegistry


class InMemoryDatasetRegistry(IDatasetRegistry):
    def __init__(self) -> None:
        self._datasets: dict[DatasetId, DatasetDescriptor] = {}

    def register(self, descriptor: DatasetDescriptor) -> None:
        self._datasets[descriptor.dataset_id] = descriptor

    def find(self, dataset_id: DatasetId) -> DatasetDescriptor | None:
        return self._datasets.get(dataset_id)

    def all(self) -> tuple[DatasetDescriptor, ...]:
        return tuple(self._datasets.values())

    def update_status(self, dataset_id: DatasetId, status: DatasetStatus) -> None:
        descriptor = self._datasets.get(dataset_id)
        if descriptor is not None:
            self._datasets[dataset_id] = DatasetDescriptor(
                dataset_id=descriptor.dataset_id,
                name=descriptor.name,
                hf_path=descriptor.hf_path,
                description=descriptor.description,
                expected_size_bytes=descriptor.expected_size_bytes,
                license=descriptor.license,
                formats=descriptor.formats,
                official_url=descriptor.official_url,
                status=status,
                versions=descriptor.versions,
            )
