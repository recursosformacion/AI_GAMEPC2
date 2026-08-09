from pathlib import Path

from src.osap.application.composers_service import ComposersService
from src.osap.application.votes_service import VotesService
from src.osap.bootstrap.configuration import Configuration, load_configuration
from src.osap.bootstrap.container import Container
from src.osap.domain.event import Event
from src.osap.domain.ranking_config import RankingConfig
from src.osap.infrastructure.adapters.export.musicxml import MusicXmlExporter
from src.osap.infrastructure.adapters.library.local import LocalLibrary
from src.osap.infrastructure.adapters.validation import BasicValidator
from src.osap.infrastructure.auth import AuthenticationManager, SecureCredentialStore
from src.osap.infrastructure.auth.service_token_provider import ClientCredentialsServiceTokenProvider
from src.osap.infrastructure.auth.token_authenticator import JwtAuthenticator
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
from src.osap.infrastructure.persistence.storage_vote_store import StorageVoteStore
from src.osap.infrastructure.pipeline import PipelineEngine
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import load_definition
from src.osap.infrastructure.providers.fetchers import (
    GitHubFetcher,
    MediaWikiFetcher,
    MusicBrainzFetcher,
    MutopiaFetcher,
    OmrStorageFetcher,
)
from src.osap.infrastructure.rankings import DefaultRankingEngine
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerClient
from src.osap.infrastructure.storage.work_store import StorageWorkStore
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
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition_path=providers_root / "mutopia",
            fetcher=MutopiaFetcher(),
        )
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition_path=providers_root / "musicbrainz",
            fetcher=MusicBrainzFetcher(),
        )
    )
    container.register_catalog_provider(LocalCatalogProvider(Path(config.library_root)))

    # Register metadata of EVERY declared provider (wired or not) so Discover/Sources
    # can list them all. `wired` tells whether the provider is registered as active.
    active_ids = {p.provider_id.value for p in container.catalog_manager().providers()}
    defined: list[tuple[str, str, str, bool]] = []
    for child in sorted(providers_root.iterdir()):
        if child.is_dir() and (child / "provider.yaml").exists():
            try:
                d = load_definition(child)
            except Exception:
                continue
            defined.append((d.id, d.name, d.base_url, d.id in active_ids))
    container.set_defined_providers(tuple(defined))

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

    # --- votes & statistics (v1) --------------------------------------------
    # Los votos y las estadísticas viven en osap-storage (no en una BD de osap-api).
    # osap-api se autentica frente a storage con identidad de servicio (least privilege).
    storage_base = config.omr_base_url or "https://storage.openmusicrepository.com"
    service_token_provider = ClientCredentialsServiceTokenProvider(
        client_id=config.service_client_id or "osap-api",
        client_secret=config.service_client_secret or "",
        token_url=config.osap_auth_token_url or "https://auth.osap/oauth/token",
    )
    vote_store = StorageVoteStore(base_url=storage_base, token_provider=service_token_provider)
    work_store = StorageWorkStore(base_url=storage_base, token_provider=service_token_provider)
    authenticator = JwtAuthenticator()
    votes_service = VotesService(vote_store, work_store, authenticator)
    container.set_vote_store(vote_store)
    container.set_work_store(work_store)
    container.set_authenticator(authenticator)
    container.set_votes(votes_service)

    # --- compositores (consulta pública + fusión admin) ----------------------
    # Consulta usa el service client normal (storage:read). La fusión usa un service client
    # administrativo separado (storage:admin) — osap-api NO recibe storage:admin por defecto.
    composer_client = StorageComposerClient(
        base_url=storage_base,
        token_provider=service_token_provider,
        admin_token_provider=ClientCredentialsServiceTokenProvider(
            client_id=config.admin_client_id or "osap-composer-admin-service",
            client_secret=config.admin_client_secret or "",
            token_url=config.osap_auth_token_url or "https://auth.osap/oauth/token",
        ),
    )
    composers_service = ComposersService(composer_client, authenticator)
    container.set_composers(composers_service)

    # Consumir user.deleted (osap-auth): anonimiza votos y conserva el agregado.
    def _on_user_deleted(event: Event) -> None:
        votes_service.handle_user_deleted(str(event.payload.get("user_id")))

    event_bus.subscribe("user.deleted", _on_user_deleted)
    return container
