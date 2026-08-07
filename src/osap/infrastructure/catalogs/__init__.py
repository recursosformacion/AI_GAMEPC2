from .cpdl import CPDLCatalogProvider
from .filesystem import FilesystemCatalogProvider
from .local import LocalCatalogProvider
from .remote.remote_catalog_provider import RemoteCatalogProvider

__all__ = [
    "RemoteCatalogProvider",
    "CPDLCatalogProvider",
    "LocalCatalogProvider",
    "FilesystemCatalogProvider",
]
