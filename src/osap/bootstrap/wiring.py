from pathlib import Path

from src.osap.bootstrap.configuration import Configuration
from src.osap.bootstrap.container import Container
from src.osap.domain.dataset_descriptor import DatasetDescriptor
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.value_objects import DatasetId
from src.osap.infrastructure.adapters.export.musicxml import MusicXmlExporter
from src.osap.infrastructure.adapters.library.local import LocalLibrary
from src.osap.infrastructure.adapters.validation import BasicValidator
from src.osap.infrastructure.auth import AuthenticationManager, SecureCredentialStore
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.catalogs import (
    IMSLPCatalogProvider,
    LocalCatalogProvider,
    OpenScoreCatalogProvider,
    PdmxCatalogProvider,
)
from src.osap.infrastructure.datasets import InMemoryDatasetRegistry
from src.osap.infrastructure.datasets.dataset_manager import DatasetManager
from src.osap.infrastructure.datasets.dataset_settings import DatasetSettings
from src.osap.infrastructure.dedup import DuplicateResolver
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.infrastructure.github import GitHubClient
from src.osap.infrastructure.hf.hf_dataset_installer import HuggingFaceDatasetInstaller
from src.osap.infrastructure.jobs import InMemoryJobEngine
from src.osap.infrastructure.mediawiki import MediaWikiClient
from src.osap.infrastructure.merge import MergeEngine
from src.osap.infrastructure.metrics import InMemoryMetricsCollector
from src.osap.infrastructure.pipeline import PipelineEngine
from src.osap.infrastructure.rankings import DefaultRankingEngine
from src.osap.infrastructure.user_profile import InMemoryUserProfileStore

DEFAULT_PROVIDER_ORDER = (
    "local_library",
    "openscore",
    "cpdl",
    "imslp",
    "pdmx",
)


def wire(container: Container, configuration: Configuration | None = None) -> Container:
    config = configuration or Configuration()

    github = GitHubClient(
        token=config.github_token,
        timeout=config.github_timeout,
        retries=config.github_retries,
        cache=InMemoryCache() if config.github_cache else None,
    )

    # All sources are plain ICatalogProvider implementations. Adding a new
    # catalog only requires registering another implementation here.
    container.register_catalog_provider(IMSLPCatalogProvider(MediaWikiClient(verify=config.imslp_verify_ssl)))
    container.register_catalog_provider(OpenScoreCatalogProvider(github, config.openscore_repos))
    container.register_catalog_provider(
        PdmxCatalogProvider(
            csv_url=config.pdmx_csv_url,
            index_path=Path(config.pdmx_index_path),
            download_base=config.pdmx_download_base,
        )
    )
    container.register_catalog_provider(LocalCatalogProvider(Path(config.library_root)))

    container.register_library(LocalLibrary(Path(config.library_root)))
    container.register_exporter(MusicXmlExporter())

    container.set_ranking_engine(DefaultRankingEngine())
    container.set_ranking_config(RankingConfig(provider_order=DEFAULT_PROVIDER_ORDER))
    container.set_validator(BasicValidator())

    event_bus = InMemoryEventBus()
    metrics = InMemoryMetricsCollector()
    container.set_platform(event_bus, metrics)
    container.set_cache(InMemoryCache())
    container.set_user_profile_store(InMemoryUserProfileStore())
    container.set_job_engine(InMemoryJobEngine(event_bus))
    container.set_pipeline_engine(PipelineEngine(event_bus))
    container.set_duplicate_resolver(DuplicateResolver())
    container.set_merge_engine(MergeEngine())

    master_key = config.credentials_key or "osap-local-dev-key"
    auth_store = SecureCredentialStore(Path(config.credentials_path), master_key)
    container.set_authentication_manager(AuthenticationManager(auth_store))

    registry = InMemoryDatasetRegistry()
    registry.register(
        DatasetDescriptor(
            dataset_id=DatasetId("pdmx"),
            name="PDMX",
            hf_path="openmusic/pdmx",
            expected_size_bytes=40_000_000_000,
            license="Public Domain",
            formats=(OutputFormat.MUSICXML,),
        )
    )
    dataset_settings = DatasetSettings(cache_dir=config.datasets_cache_dir)
    dataset_manager = DatasetManager(registry, HuggingFaceDatasetInstaller(), dataset_settings)
    container.set_dataset_manager(dataset_manager)
    return container
