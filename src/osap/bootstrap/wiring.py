from pathlib import Path

from src.osap.bootstrap.configuration import Configuration, load_configuration
from src.osap.bootstrap.container import Container
from src.osap.domain.ranking_config import RankingConfig
from src.osap.infrastructure.adapters.export.musicxml import MusicXmlExporter
from src.osap.infrastructure.adapters.library.local import LocalLibrary
from src.osap.infrastructure.adapters.validation import BasicValidator
from src.osap.infrastructure.auth import AuthenticationManager, SecureCredentialStore
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.catalogs import LocalCatalogProvider
from src.osap.infrastructure.catalogs.remote.remote_catalog_provider import RemoteCatalogProvider
from src.osap.infrastructure.dedup import DuplicateResolver
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.infrastructure.github import GitHubClient
from src.osap.infrastructure.jobs import InMemoryJobEngine
from src.osap.infrastructure.mediawiki import MediaWikiClient
from src.osap.infrastructure.merge import MergeEngine
from src.osap.infrastructure.metrics import InMemoryMetricsCollector
from src.osap.infrastructure.pipeline import PipelineEngine
from src.osap.infrastructure.providers.fetchers import GitHubFetcher, MediaWikiFetcher, OmrStorageFetcher
from src.osap.infrastructure.rankings import DefaultRankingEngine
from src.osap.infrastructure.user_profile import InMemoryUserProfileStore

DEFAULT_PROVIDER_ORDER = (
    "local_library",
    "openscore",
    "cpdl",
    "imslp",
    "openmusicrepository",
)


def wire(container: Container, configuration: Configuration | None = None) -> Container:
    config = configuration or load_configuration()

    github = GitHubClient(
        token=config.github_token,
        timeout=config.github_timeout,
        retries=config.github_retries,
        cache=InMemoryCache() if config.github_cache else None,
    )

    # All sources are plain ICatalogProvider implementations. Level 1 providers are
    # fully described by their YAML definition. Level 2 providers add a light fetcher
    # (MediaWiki, GitHub) that returns normalized contract JSON through the same mapping.
    providers_root = Path(__file__).resolve().parents[3] / "providers"
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition_path=providers_root / "imslp",
            fetcher=MediaWikiFetcher(MediaWikiClient(verify=config.imslp_verify_ssl)),
        )
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition_path=providers_root / "openscore",
            fetcher=GitHubFetcher(github, config.openscore_repos),
        )
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition_path=providers_root / "omr",
            base_url=config.omr_base_url,
            fetcher=OmrStorageFetcher(
                base_url=config.omr_base_url or "https://storage.openmusicrepository.com"
            ),
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
    return container
