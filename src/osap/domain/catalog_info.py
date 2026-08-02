from dataclasses import dataclass

from .catalog_status import CatalogStatus
from .value_objects import CatalogId, ProviderId


@dataclass(frozen=True)
class CatalogInfo:
    """Description of a catalog managed by the CatalogManager."""

    catalog_id: CatalogId
    name: str
    provider_id: ProviderId
    source: str
    status: CatalogStatus
    version: str | None = None
    item_count: int | None = None
