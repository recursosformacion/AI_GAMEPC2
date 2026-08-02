from src.osap.domain.errors import ResourceNeedsApprovalError, ResourceUnavailableError
from src.osap.domain.resource import Resource, ResourceStatus
from src.osap.infrastructure.resources.resource_provider import IResourceProvider


class ResourceManager:
    """Manages any external resource used by OSAP (datasets, catalogs, models,
    caches, knowledge bases, ...).

    Decides automatically whether a resource exists, is installed, is up to
    date, needs downloading, can be streamed or should use a local copy. The
    user only needs to approve when strictly necessary (too large, no
    connection, license acceptance or version conflict).
    """

    def __init__(
        self,
        providers: tuple[IResourceProvider, ...] = (),
        *,
        auto_install: bool = True,
        auto_install_size_threshold: int | None = None,
        network_available: bool = True,
    ) -> None:
        self._providers: dict[str, IResourceProvider] = {}
        for provider in providers:
            self.register(provider)
        self._auto_install = auto_install
        self._size_threshold = auto_install_size_threshold
        self._network = network_available

    def register(self, provider: IResourceProvider) -> None:
        self._providers[provider.resource_id] = provider

    def list(self) -> tuple[Resource, ...]:
        return tuple(provider.metadata() for provider in self._providers.values())

    def status(self, resource_id: str) -> ResourceStatus:
        return self._find(resource_id).status()

    def metadata(self, resource_id: str) -> Resource:
        return self._find(resource_id).metadata()

    def ensure(self, resource_id: str, *, streaming: bool = False) -> Resource:
        """Make sure a resource is usable, installing it transparently if needed."""
        provider = self._find(resource_id)
        status = provider.status()
        if status in (ResourceStatus.INSTALLED, ResourceStatus.INDEX_ONLY, ResourceStatus.PARTIAL):
            return provider.metadata()
        return self._install(provider, streaming=streaming)

    def install(self, resource_id: str, *, index_only: bool = False) -> Resource:
        return self._install(self._find(resource_id), index_only=index_only)

    def update(self, resource_id: str) -> Resource:
        provider = self._find(resource_id)
        provider.update()
        return provider.metadata()

    def remove(self, resource_id: str) -> None:
        self._find(resource_id).remove()

    def _install(self, provider: IResourceProvider, *, index_only: bool = False, streaming: bool = False) -> Resource:
        resource = provider.metadata()
        if not self._auto_install:
            raise ResourceUnavailableError(f"Resource '{resource.name}' is not installed")
        if not self._network:
            raise ResourceUnavailableError(f"Resource '{resource.name}' requires a network connection")
        if self._size_threshold is not None and resource.size and resource.size > self._size_threshold:
            raise ResourceNeedsApprovalError(
                f"Resource '{resource.name}' is {resource.size} bytes; approval is required to download it"
            )
        try:
            provider.install(index_only=index_only or streaming)
        except NotImplementedError as exc:
            raise ResourceUnavailableError(f"Resource '{resource.name}' cannot be installed yet") from exc
        return provider.metadata()

    def _find(self, resource_id: str) -> IResourceProvider:
        try:
            return self._providers[resource_id]
        except KeyError as exc:
            raise ResourceUnavailableError(f"Unknown resource: {resource_id}") from exc
