from abc import ABC, abstractmethod
from collections.abc import Callable

from src.osap.domain.dataset_descriptor import DatasetDescriptor
from src.osap.domain.value_objects import DatasetId

from .dataset_settings import DatasetSettings

ProgressCallback = Callable[[int, int | None, str], None]


class IDatasetInstaller(ABC):
    """Downloads and manages dataset files (e.g. via Hugging Face Datasets).

    Never downloads automatically; only on explicit user request. Supports
    progress reporting, resume, hash verification, disk-space checks and cancel.
    The underlying library is confined to infrastructure.
    """

    @abstractmethod
    def install(self, descriptor: DatasetDescriptor, settings: DatasetSettings, on_progress: ProgressCallback) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self, descriptor: DatasetDescriptor, settings: DatasetSettings, on_progress: ProgressCallback) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove(self, dataset_id: DatasetId, settings: DatasetSettings) -> None:
        raise NotImplementedError

    @abstractmethod
    def verify(self, descriptor: DatasetDescriptor, settings: DatasetSettings) -> bool:
        raise NotImplementedError

    @abstractmethod
    def location(self, dataset_id: DatasetId, settings: DatasetSettings) -> str | None:
        raise NotImplementedError
