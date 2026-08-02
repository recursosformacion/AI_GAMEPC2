from src.osap.domain.dataset_descriptor import DatasetDescriptor
from src.osap.domain.dataset_mode import DatasetMode
from src.osap.domain.dataset_status import DatasetStatus
from src.osap.domain.errors import DatasetOperationError
from src.osap.domain.value_objects import DatasetId
from src.osap.infrastructure.datasets.dataset_installer import IDatasetInstaller, ProgressCallback
from src.osap.infrastructure.datasets.dataset_registry import IDatasetRegistry
from src.osap.infrastructure.datasets.dataset_settings import DatasetSettings

_NOOP: ProgressCallback = lambda done, total, stage: None  # noqa: E731

_LARGE_THRESHOLD_BYTES = 1_000_000_000  # 1 GB → prefer streaming


class DatasetManager:
    """Facade over the dataset registry and installer.

    Manages availability automatically: the user never installs a dataset.
    OSAP decides whether to download, stream or use the cache, reusing the
    official Hugging Face cache. Never downloads the same dataset twice.
    """

    def __init__(self, registry: IDatasetRegistry, installer: IDatasetInstaller, settings: DatasetSettings) -> None:
        self._registry = registry
        self._installer = installer
        self._settings = settings

    def list(self) -> tuple[DatasetDescriptor, ...]:
        return self._registry.all()

    def info(self, dataset_id: DatasetId) -> DatasetDescriptor | None:
        return self._registry.find(dataset_id)

    def status(self, dataset_id: DatasetId) -> DatasetStatus:
        return self._require(dataset_id).status

    def ensure_available(self, dataset_id: DatasetId, on_progress: ProgressCallback = _NOOP) -> DatasetStatus:
        """Guarantee the dataset is usable, downloading/streaming transparently.

        Returns the resulting availability state. The caller does not need to
        know whether it was already cached, just streamed or freshly downloaded.
        """
        descriptor = self._require(dataset_id)
        status = descriptor.status

        if status in (DatasetStatus.READY, DatasetStatus.STREAMING):
            if self._settings.auto_update:
                self.update(dataset_id, on_progress)
            return status

        if self._settings.offline:
            return DatasetStatus.NOT_PRESENT

        mode = self._resolve_mode(descriptor)
        self._registry.update_status(dataset_id, DatasetStatus.DOWNLOADING)
        on_progress(0, None, "downloading metadata")

        try:
            effective = DatasetSettings(
                cache_dir=self._settings.cache_dir,
                mode=mode,
                num_proc=self._settings.num_proc,
                download_mode=self._settings.download_mode,
                max_disk_usage_bytes=self._settings.max_disk_usage_bytes,
            )
            self._installer.install(descriptor, effective, on_progress)
            target = DatasetStatus.STREAMING if mode is DatasetMode.STREAMING else DatasetStatus.READY
            self._registry.update_status(dataset_id, target)
            on_progress(100, None, target.value)
            return target
        except Exception as exc:
            self._registry.update_status(dataset_id, DatasetStatus.ERROR)
            raise DatasetOperationError(f"Could not make dataset '{descriptor.name}' available") from exc

    def install(self, dataset_id: DatasetId, on_progress: ProgressCallback = _NOOP) -> None:
        self.ensure_available(dataset_id, on_progress)

    def update(self, dataset_id: DatasetId, on_progress: ProgressCallback = _NOOP) -> None:
        descriptor = self._require(dataset_id)
        status = descriptor.status
        if status is DatasetStatus.NOT_PRESENT:
            self.ensure_available(dataset_id, on_progress)
            return
        mode = self._resolve_mode(descriptor)
        self._registry.update_status(dataset_id, DatasetStatus.DOWNLOADING)
        try:
            self._installer.update(descriptor, self._settings, on_progress)
            target = DatasetStatus.STREAMING if mode is DatasetMode.STREAMING else DatasetStatus.READY
            self._registry.update_status(dataset_id, target)
        except Exception:
            self._registry.update_status(dataset_id, DatasetStatus.ERROR)
            raise

    def remove(self, dataset_id: DatasetId) -> None:
        self._installer.remove(dataset_id, self._settings)
        self._registry.update_status(dataset_id, DatasetStatus.NOT_PRESENT)

    def verify(self, dataset_id: DatasetId) -> bool:
        return self._installer.verify(self._require(dataset_id), self._settings)

    def repair(self, dataset_id: DatasetId, on_progress: ProgressCallback = _NOOP) -> None:
        self.remove(dataset_id)
        self.ensure_available(dataset_id, on_progress)

    def location(self, dataset_id: DatasetId) -> str | None:
        return self._installer.location(dataset_id, self._settings)

    def is_available(self, dataset_id: DatasetId) -> bool:
        try:
            return self.status(dataset_id) in (DatasetStatus.READY, DatasetStatus.STREAMING)
        except DatasetOperationError:
            return False

    def _resolve_mode(self, descriptor: DatasetDescriptor) -> DatasetMode:
        if self._settings.mode is DatasetMode.AUTO:
            if descriptor.expected_size_bytes and descriptor.expected_size_bytes > _LARGE_THRESHOLD_BYTES:
                return DatasetMode.STREAMING
            return DatasetMode.CACHE
        return self._settings.mode

    def _require(self, dataset_id: DatasetId) -> DatasetDescriptor:
        descriptor = self._registry.find(dataset_id)
        if descriptor is None:
            raise DatasetOperationError(f"Unknown dataset: {dataset_id.value}")
        return descriptor
