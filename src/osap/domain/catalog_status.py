from enum import Enum


class CatalogStatus(Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPDATED = "updated"
    STALE = "stale"
    ERROR = "error"
