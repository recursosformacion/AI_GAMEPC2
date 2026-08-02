import pytest

from src.osap.domain.errors import ResourceNeedsApprovalError, ResourceUnavailableError
from src.osap.domain.resource import Resource, ResourceKind, ResourceStatus
from src.osap.domain.value_objects import ProviderId, ResourceId
from src.osap.infrastructure.resources.resource_manager import ResourceManager
from src.osap.infrastructure.resources.resource_provider import IResourceProvider


class FakeResourceProvider(IResourceProvider):
    def __init__(self, resource_id: str, *, installed: bool = False, size: int | None = None) -> None:
        self._id = resource_id
        self._installed = installed
        self._size = size
        self.installs = 0

    @property
    def resource_id(self) -> str:
        return self._id

    def install(self, index_only: bool = False) -> None:
        self.installs += 1
        self._installed = True

    def update(self) -> None:
        pass

    def remove(self) -> None:
        self._installed = False

    def exists(self) -> bool:
        return self._installed

    def status(self) -> ResourceStatus:
        return ResourceStatus.INSTALLED if self._installed else ResourceStatus.NOT_INSTALLED

    def metadata(self) -> Resource:
        return Resource(
            resource_id=ResourceId(self._id),
            name=self._id,
            kind=ResourceKind.DATASET,
            provider=ProviderId("test"),
            status=self.status(),
            size=self._size,
        )


class TestResourceManager:
    def test_ensure_installed_noop(self) -> None:
        provider = FakeResourceProvider("pdmx", installed=True)
        manager = ResourceManager(providers=(provider,))
        resource = manager.ensure("pdmx")
        assert resource.status == ResourceStatus.INSTALLED
        assert provider.installs == 0

    def test_ensure_auto_installs(self) -> None:
        provider = FakeResourceProvider("pdmx")
        manager = ResourceManager(providers=(provider,))
        manager.ensure("pdmx")
        assert provider.installs == 1
        assert provider.status() == ResourceStatus.INSTALLED

    def test_auto_install_disabled_raises(self) -> None:
        provider = FakeResourceProvider("pdmx")
        manager = ResourceManager(providers=(provider,), auto_install=False)
        with pytest.raises(ResourceUnavailableError):
            manager.ensure("pdmx")

    def test_oversized_requires_approval(self) -> None:
        provider = FakeResourceProvider("pdmx", size=10_000)
        manager = ResourceManager(providers=(provider,), auto_install_size_threshold=1_000)
        with pytest.raises(ResourceNeedsApprovalError):
            manager.ensure("pdmx")
        assert provider.installs == 0

    def test_no_network_raises(self) -> None:
        provider = FakeResourceProvider("pdmx")
        manager = ResourceManager(providers=(provider,), network_available=False)
        with pytest.raises(ResourceUnavailableError):
            manager.ensure("pdmx")

    def test_list(self) -> None:
        manager = ResourceManager(providers=(FakeResourceProvider("pdmx"),))
        assert [r.resource_id.value for r in manager.list()] == ["pdmx"]

    def test_unknown_raises(self) -> None:
        with pytest.raises(ResourceUnavailableError):
            ResourceManager().ensure("nope")
