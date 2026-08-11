import json
from pathlib import Path
from typing import Any

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
from src.osap.infrastructure.auth.auth_proxy_client import AuthProxyClient
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
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    ProviderDefinition,
    load_definition,
    load_definition_from_config,
)
from src.osap.infrastructure.providers.fetchers import (
    GitHubFetcher,
    MediaWikiFetcher,
    MusicBrainzFetcher,
    MutopiaFetcher,
    OmrStorageFetcher,
)
from src.osap.infrastructure.rankings import DefaultRankingEngine
from src.osap.infrastructure.state.op_store import build_op_store
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


_LOCAL_ROUTES = {
    "storage": "http://127.0.0.1:8000",
    "auth_token": "http://127.0.0.1:8200/oauth/token",
    "auth_base": "http://127.0.0.1:8200",
}
_REAL_ROUTES = {
    "storage": "https://storage.openmusicrepository.com",
    "auth_token": "https://auth.osap/oauth/token",
    "auth_base": "https://auth.osap",
}


def _routes(deployment: str, dev_mode: int) -> tuple[dict[str, str], bool]:
    """Decide las rutas (storage/auth) y si es solo lectura según entorno y dev_mode.

    - deployment == "prod": rutas reales, escribible.
    - deployment == "dev": dev_mode=0 → local; dev_mode=1 → real y SOLO lectura.
    """
    if deployment == "prod":
        return _REAL_ROUTES, False
    use_real = dev_mode == 1
    return (_REAL_ROUTES if use_real else _LOCAL_ROUTES), use_real


def _provider_definition(
    store: Any,
    provider_id: str,
    fallback_path: Path,
    base_url: str | None = None,
) -> ProviderDefinition:
    """Carga la definición del proveedor desde la BD (dev); si no, desde YAML (prod)."""
    try:
        row = store.get_provider(provider_id)
        if row and row.get("config"):
            definition = load_definition_from_config(provider_id, json.loads(str(row["config"])))
        else:
            definition = load_definition(fallback_path)
    except Exception:  # noqa: BLE001
        definition = load_definition(fallback_path)
    if base_url:
        from dataclasses import replace

        return replace(definition, base_url=base_url.rstrip("/"))
    return definition


def _db_provider_metadata(container: Container) -> list[tuple[str, str, str | None, bool]]:
    try:
        store = build_op_store(**container.op_store_config())
        rows = store.list_providers()
        if not rows:
            return []
        out: list[tuple[str, str, str | None, bool]] = []
        for row in rows:
            out.append(
                (
                    str(row.get("provider_id") or ""),
                    str(row.get("name") or ""),
                    str(row.get("base_url")) if row.get("base_url") else None,
                    bool(row.get("wired")),
                )
            )
        return out
    except Exception:  # noqa: BLE001
        return []


def wire(container: Container, configuration: Configuration | None = None) -> Container:
    config = configuration or load_configuration()
    routes, storage_read_only = _routes(config.deployment, config.dev_mode)
    storage_base = routes["storage"]
    auth_token_url = routes["auth_token"]
    auth_base = routes["auth_base"]

    github = GitHubClient(
        token=config.github_token,
        timeout=config.github_timeout,
        retries=config.github_retries,
        cache=InMemoryCache() if config.github_cache else None,
    )

    # All sources are plain ICatalogProvider implementations. Level 1 providers are
    # fully described by their definition (leída de la BD operativa en dev, de los
    # YAML en prod). Level 2 providers añaden un fetcher (MediaWiki, GitHub) que
    # devuelve JSON normalizado por el mismo mapping.
    providers_root = Path(__file__).resolve().parents[3] / "providers"
    op_store = build_op_store(
        host=config.osap_api_db_host,
        user=config.osap_api_db_user,
        password=config.osap_api_db_password,
        database=config.osap_api_db_name,
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition=_provider_definition(op_store, "imslp", providers_root / "imslp"),
            fetcher=MediaWikiFetcher(MediaWikiClient(verify=config.imslp_verify_ssl)),
        )
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition=_provider_definition(op_store, "openscore", providers_root / "openscore"),
            fetcher=GitHubFetcher(github, config.openscore_repos),
        )
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition=_provider_definition(op_store, "omr", providers_root / "omr", base_url=storage_base),
            base_url=storage_base,
            fetcher=OmrStorageFetcher(base_url=storage_base),
        )
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition=_provider_definition(op_store, "mutopia", providers_root / "mutopia"),
            fetcher=MutopiaFetcher(),
        )
    )
    container.register_catalog_provider(
        RemoteCatalogProvider(
            definition=_provider_definition(op_store, "musicbrainz", providers_root / "musicbrainz"),
            fetcher=MusicBrainzFetcher(),
        )
    )
    container.register_catalog_provider(LocalCatalogProvider(Path(config.library_root)))

    # Register metadata of EVERY declared provider (wired or not) so Discover/Sources
    # can list them all. `wired` tells whether the provider is registered as active.
    # Se lee de la BD operativa si está sembrada (dev); si no, de los YAML (prod).
    active_ids = {p.provider_id.value for p in container.catalog_manager().providers()}
    defined: list[tuple[str, str, str, bool]] = []
    db_providers = _db_provider_metadata(container)
    if db_providers:
        for provider_id, name, base_url, wired in db_providers:
            defined.append((provider_id, name, base_url or "", wired))
    else:
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

    # --- registro/verificación de usuario (proxy público a osap-auth) ---------
    auth_proxy = AuthProxyClient(base_url=auth_base)
    container.set_auth_proxy(auth_proxy)

    # --- votes & statistics (v1) --------------------------------------------
    # Los votos y las estadísticas viven en osap-storage (no en una BD de osap-api).
    # osap-api se autentica frente a storage con identidad de servicio (least privilege).
    service_token_provider = ClientCredentialsServiceTokenProvider(
        client_id=config.service_client_id or "osap-api",
        client_secret=config.service_client_secret or "",
        token_url=auth_token_url,
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
    target = (
        "local"
        if storage_base.startswith("http://127.") or storage_base.startswith("http://localhost")
        else "remote"
    )
    container.set_storage_info(target, storage_read_only)
    container.set_op_store_config(
        {
            "host": config.osap_api_db_host,
            "user": config.osap_api_db_user,
            "password": config.osap_api_db_password,
            "database": config.osap_api_db_name,
        }
    )
    composer_client = StorageComposerClient(
        base_url=storage_base,
        token_provider=service_token_provider,
        admin_token_provider=ClientCredentialsServiceTokenProvider(
            client_id=config.admin_client_id or "osap-composer-admin-service",
            client_secret=config.admin_client_secret or "",
            token_url=auth_token_url,
        ),
    )
    composers_service = ComposersService(composer_client, authenticator, read_only=storage_read_only)
    container.set_composers(composers_service)

    # Consumir user.deleted (osap-auth): anonimiza votos y conserva el agregado.
    def _on_user_deleted(event: Event) -> None:
        votes_service.handle_user_deleted(str(event.payload.get("user_id")))

    event_bus.subscribe("user.deleted", _on_user_deleted)
    return container
