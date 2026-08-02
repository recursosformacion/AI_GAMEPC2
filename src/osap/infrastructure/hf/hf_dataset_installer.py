import importlib
import threading
from pathlib import Path
from typing import Any

from src.osap.domain.dataset_descriptor import DatasetDescriptor
from src.osap.domain.dataset_mode import DatasetMode
from src.osap.domain.errors import DatasetCancelledError, DatasetOperationError
from src.osap.domain.value_objects import DatasetId
from src.osap.infrastructure.datasets.dataset_installer import IDatasetInstaller, ProgressCallback
from src.osap.infrastructure.datasets.dataset_settings import DatasetSettings


class HuggingFaceDatasetInstaller(IDatasetInstaller):
    """Installs datasets through Hugging Face Datasets.

    Respects `settings.mode`: STREAMING loads metadata without downloading the
    full dataset; CACHE downloads and caches for fast queries. AUTO is
    resolved by the DatasetManager before calling install. The official
    Hugging Face cache is reused; OSAP never implements its own cache.
    """

    def __init__(self) -> None:
        self._cancel = threading.Event()

    def install(self, descriptor: DatasetDescriptor, settings: DatasetSettings, on_progress: ProgressCallback) -> None:
        self._cancel.clear()
        streaming = settings.mode is DatasetMode.STREAMING
        if not streaming:
            self._check_disk_space(descriptor, settings)
        on_progress(0, None, "started")
        self._check_cancelled()
        module = self._datasets_module()
        self._check_cancelled()
        on_progress(20, None, "downloading")
        kwargs: dict[str, object] = {}
        if settings.cache_dir:
            kwargs["cache_dir"] = settings.cache_dir
        if settings.num_proc:
            kwargs["num_proc"] = settings.num_proc
        if streaming:
            kwargs["streaming"] = True
        else:
            kwargs["download_mode"] = settings.download_mode
        module.load_dataset(descriptor.hf_path, **kwargs)
        self._check_cancelled()
        on_progress(90, None, "verifying")
        if not streaming and not self.verify(descriptor, settings):
            raise DatasetOperationError(f"Verification failed for dataset {descriptor.name}")
        on_progress(100, None, "done")

    def update(self, descriptor: DatasetDescriptor, settings: DatasetSettings, on_progress: ProgressCallback) -> None:
        self._cancel.clear()
        on_progress(0, None, "updating")
        module = self._datasets_module()
        module.load_dataset(
            descriptor.hf_path,
            cache_dir=settings.cache_dir,
            num_proc=settings.num_proc,
            download_mode="force_redownload",
        )
        on_progress(100, None, "done")

    def remove(self, dataset_id: DatasetId, settings: DatasetSettings) -> None:
        if not settings.cache_dir:
            return
        root = Path(settings.cache_dir)
        for candidate in root.rglob(f"*{dataset_id.value}*"):
            if candidate.is_dir():
                self._rmtree(candidate)

    def verify(self, descriptor: DatasetDescriptor, settings: DatasetSettings) -> bool:
        if not settings.cache_dir:
            return False
        root = Path(settings.cache_dir)
        if not root.exists():
            return False
        return any(descriptor.hf_path.split("/")[-1] in p.name for p in root.rglob("*") if p.is_dir())

    def location(self, dataset_id: DatasetId, settings: DatasetSettings) -> str | None:
        if not settings.cache_dir:
            return None
        root = Path(settings.cache_dir)
        matches = [p for p in root.rglob(f"*{dataset_id.value}*") if p.is_dir()]
        return str(matches[0]) if matches else None

    def cancel(self) -> None:
        self._cancel.set()

    def _check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise DatasetCancelledError("Dataset operation cancelled")

    @staticmethod
    def _check_disk_space(descriptor: DatasetDescriptor, settings: DatasetSettings) -> None:
        if (
            settings.max_disk_usage_bytes
            and descriptor.expected_size_bytes
            and descriptor.expected_size_bytes > settings.max_disk_usage_bytes
        ):
            raise DatasetOperationError(
                f"Dataset {descriptor.name} requires {descriptor.expected_size_bytes} bytes, "
                f"but max disk usage is {settings.max_disk_usage_bytes}"
            )

    @staticmethod
    def _datasets_module() -> Any:
        try:
            return importlib.import_module("datasets")
        except ImportError as exc:
            raise DatasetOperationError(
                "The 'datasets' library is required. Install it with: pip install 'osap[datasets]'"
            ) from exc

    @staticmethod
    def _rmtree(path: Path) -> None:
        for child in path.iterdir():
            if child.is_dir():
                HuggingFaceDatasetInstaller._rmtree(child)
            else:
                child.unlink()
        path.rmdir()
