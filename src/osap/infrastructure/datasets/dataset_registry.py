from abc import ABC, abstractmethod

from src.osap.domain.dataset_descriptor import DatasetDescriptor
from src.osap.domain.dataset_status import DatasetStatus
from src.osap.domain.value_objects import DatasetId


class IDatasetRegistry(ABC):
    """Independent registry of dataset descriptors (name, size, license,
    formats, url, status, versions). Never hard-codes a specific dataset."""

    @abstractmethod
    def register(self, descriptor: DatasetDescriptor) -> None:
        raise NotImplementedError

    @abstractmethod
    def find(self, dataset_id: DatasetId) -> DatasetDescriptor | None:
        raise NotImplementedError

    @abstractmethod
    def all(self) -> tuple[DatasetDescriptor, ...]:
        raise NotImplementedError

    @abstractmethod
    def update_status(self, dataset_id: DatasetId, status: DatasetStatus) -> None:
        raise NotImplementedError
