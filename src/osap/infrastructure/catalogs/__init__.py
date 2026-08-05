from .cpdl import CPDLCatalogProvider
from .filesystem import FilesystemCatalogProvider
from .imslp import IMSLPCatalogProvider
from .local import LocalCatalogProvider
from .omr import OmrCatalogProvider
from .openscore import OpenScoreCatalogProvider
from .pdmx import PdmxCatalogProvider

__all__ = [
    "IMSLPCatalogProvider",
    "OpenScoreCatalogProvider",
    "CPDLCatalogProvider",
    "LocalCatalogProvider",
    "FilesystemCatalogProvider",
    "PdmxCatalogProvider",
    "OmrCatalogProvider",
]
