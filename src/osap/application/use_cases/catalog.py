from src.osap.application.catalog_manager import CatalogManager
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.value_objects import CatalogId


class CatalogUseCase:
    def __init__(self, manager: CatalogManager) -> None:
        self.manager = manager

    def list(self) -> tuple[CatalogId, ...]:
        return self.manager.list()

    def info(self, catalog_id: CatalogId) -> CatalogInfo:
        return self.manager.info(catalog_id)

    def capabilities(self, catalog_id: CatalogId) -> CatalogCapabilities:
        return self.manager.capabilities(catalog_id)
