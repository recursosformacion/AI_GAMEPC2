import pytest

from src.osap.domain.dataset_descriptor import DatasetDescriptor, DatasetVersion
from src.osap.domain.dataset_status import DatasetStatus
from src.osap.domain.errors import DatasetOperationError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import DatasetId
from src.osap.infrastructure.datasets.dataset_installer import IDatasetInstaller, ProgressCallback
from src.osap.infrastructure.datasets.dataset_manager import DatasetManager
from src.osap.infrastructure.datasets.dataset_registry import IDatasetRegistry
from src.osap.infrastructure.datasets.dataset_settings import DatasetSettings


def _descriptor(dataset_id: str = "pdmx", ready: bool = False) -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=DatasetId(dataset_id),
        name=dataset_id,
        hf_path=f"org/{dataset_id}",
        expected_size_bytes=100,
        license="Public Domain",
        formats=(OutputFormat.MUSICXML,),
        status=DatasetStatus.READY if ready else DatasetStatus.NOT_PRESENT,
        versions=(DatasetVersion(version="1.0"),),
    )


class FakeRegistry(IDatasetRegistry):
    def __init__(self, descriptors: tuple[DatasetDescriptor, ...] = ()) -> None:
        self._d: dict[DatasetId, DatasetDescriptor] = {x.dataset_id: x for x in descriptors}

    def register(self, descriptor: DatasetDescriptor) -> None:
        self._d[descriptor.dataset_id] = descriptor

    def find(self, dataset_id: DatasetId) -> DatasetDescriptor | None:
        return self._d.get(dataset_id)

    def all(self) -> tuple[DatasetDescriptor, ...]:
        return tuple(self._d.values())

    def update_status(self, dataset_id: DatasetId, status: DatasetStatus) -> None:
        desc = self._d.get(dataset_id)
        if desc:
            self._d[dataset_id] = DatasetDescriptor(
                dataset_id=desc.dataset_id,
                name=desc.name,
                hf_path=desc.hf_path,
                description=desc.description,
                expected_size_bytes=desc.expected_size_bytes,
                license=desc.license,
                formats=desc.formats,
                official_url=desc.official_url,
                status=status,
                versions=desc.versions,
            )


class FakeInstaller(IDatasetInstaller):
    def __init__(self) -> None:
        self.installs = 0
        self.cancelled = False

    def install(self, descriptor: DatasetDescriptor, settings: DatasetSettings, on_progress: ProgressCallback) -> None:
        self.installs += 1
        on_progress(100, None, "done")

    def update(self, descriptor: DatasetDescriptor, settings: DatasetSettings, on_progress: ProgressCallback) -> None:
        on_progress(100, None, "done")

    def remove(self, dataset_id: DatasetId, settings: DatasetSettings) -> None:
        pass

    def verify(self, descriptor: DatasetDescriptor, settings: DatasetSettings) -> bool:
        return True

    def location(self, dataset_id: DatasetId, settings: DatasetSettings) -> str | None:
        return "/cache/pdmx" if dataset_id.value == "pdmx" else None


class TestDatasetManager:
    def _manager(self) -> tuple[DatasetManager, FakeRegistry, FakeInstaller]:
        registry = FakeRegistry((_descriptor(),))
        installer = FakeInstaller()
        manager = DatasetManager(registry, installer, DatasetSettings())
        return manager, registry, installer

    def test_list_and_info(self) -> None:
        manager, _, _ = self._manager()
        assert [d.dataset_id.value for d in manager.list()] == ["pdmx"]
        assert manager.info(DatasetId("pdmx")) is not None
        assert manager.status(DatasetId("pdmx")) == DatasetStatus.NOT_PRESENT

    def test_install_updates_status(self) -> None:
        manager, _, installer = self._manager()
        manager.install(DatasetId("pdmx"))
        assert installer.installs == 1
        assert manager.status(DatasetId("pdmx")) == DatasetStatus.READY

    def test_install_reports_error_status_on_failure(self) -> None:
        class Broken(FakeInstaller):
            def install(
                self, descriptor: DatasetDescriptor, settings: DatasetSettings, on_progress: ProgressCallback
            ) -> None:
                raise DatasetOperationError("boom")

        manager = DatasetManager(FakeRegistry((_descriptor(),)), Broken(), DatasetSettings())
        with pytest.raises(DatasetOperationError):
            manager.install(DatasetId("pdmx"))
        assert manager.status(DatasetId("pdmx")) == DatasetStatus.ERROR

    def test_unknown_raises(self) -> None:
        manager, _, _ = self._manager()
        with pytest.raises(DatasetOperationError):
            manager.install(DatasetId("nope"))

    def test_verify_and_location(self) -> None:
        manager, _, _ = self._manager()
        assert manager.verify(DatasetId("pdmx")) is True
        assert manager.location(DatasetId("pdmx")) == "/cache/pdmx"

    def test_remove_resets_status(self) -> None:
        manager, registry, _ = self._manager()
        registry.update_status(DatasetId("pdmx"), DatasetStatus.READY)
        manager.remove(DatasetId("pdmx"))
        assert manager.status(DatasetId("pdmx")) == DatasetStatus.NOT_PRESENT
