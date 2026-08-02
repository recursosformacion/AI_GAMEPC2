from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.value_objects import CatalogId
from src.osap.ports.catalog_provider import ICatalogProvider


class CatalogManager:
    """Registers and manages catalog providers.

    Responsibilities: register providers, install, update, query capabilities
    and list available catalogs. It never knows Hugging Face, GitHub or any
    concrete technology.
    """

    def __init__(self) -> None:
        self._providers: dict[CatalogId, ICatalogProvider] = {}

    def register(self, provider: ICatalogProvider) -> None:
        self._providers[CatalogId(provider.provider_id.value)] = provider

    def providers(self) -> tuple[ICatalogProvider, ...]:
        return tuple(self._providers.values())

    def available(self, catalog_id: CatalogId) -> bool:
        return catalog_id in self._providers

    def list(self) -> tuple[CatalogId, ...]:
        return tuple(self._providers)

    def capabilities(self, catalog_id: CatalogId) -> CatalogCapabilities:
        return self._provider(catalog_id).capabilities()

    def info(self, catalog_id: CatalogId) -> CatalogInfo:
        return self._provider(catalog_id).metadata()

    def _provider(self, catalog_id: CatalogId) -> ICatalogProvider:
        try:
            return self._providers[catalog_id]
        except KeyError as exc:
            raise ScoreResolutionError(f"Unknown catalog: {catalog_id.value}") from exc
