from src.osap.infrastructure.adapters import export, library, validation
from src.osap.infrastructure.auth import AuthenticationManager, SecureCredentialStore
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.catalogs import (
    CPDLCatalogProvider,
    FilesystemCatalogProvider,
    IMSLPCatalogProvider,
    LocalCatalogProvider,
    OpenScoreCatalogProvider,
    PdmxCatalogProvider,
)
from src.osap.infrastructure.datasets import InMemoryDatasetRegistry
from src.osap.infrastructure.dedup import DuplicateResolver
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.infrastructure.jobs import InMemoryJobEngine
from src.osap.infrastructure.merge import MergeEngine
from src.osap.infrastructure.metrics import InMemoryMetricsCollector
from src.osap.infrastructure.pipeline import PipelineEngine
from src.osap.infrastructure.rankings import DefaultRankingEngine
from src.osap.infrastructure.resources import HuggingFaceResourceProvider
from src.osap.infrastructure.user_profile import InMemoryUserProfileStore

__all__ = [
    "export",
    "library",
    "validation",
    "AuthenticationManager",
    "SecureCredentialStore",
    "IMSLPCatalogProvider",
    "OpenScoreCatalogProvider",
    "CPDLCatalogProvider",
    "LocalCatalogProvider",
    "FilesystemCatalogProvider",
    "PdmxCatalogProvider",
    "HuggingFaceResourceProvider",
    "DefaultRankingEngine",
    "InMemoryDatasetRegistry",
    "InMemoryEventBus",
    "InMemoryMetricsCollector",
    "InMemoryCache",
    "InMemoryUserProfileStore",
    "InMemoryJobEngine",
    "DuplicateResolver",
    "MergeEngine",
    "PipelineEngine",
]
