from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.evidence_engine import EvidenceEngine
from src.osap.application.export_manager import ExportManager
from src.osap.application.library_manager import LibraryManager
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.application.work_merge_service import WorkMergeService
from src.osap.application.work_resolution_engine import WorkResolutionEngine
from src.osap.application.work_resolver import WorkResolver
from src.osap.domain.ranking_config import RankingConfig
from src.osap.infrastructure.auth import AuthenticationManager
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.dedup import DuplicateResolver
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.infrastructure.jobs import InMemoryJobEngine
from src.osap.infrastructure.merge import MergeEngine
from src.osap.infrastructure.metrics import InMemoryMetricsCollector
from src.osap.infrastructure.pipeline import PipelineEngine
from src.osap.infrastructure.user_profile import InMemoryUserProfileStore
from src.osap.ports.cache import ICache
from src.osap.ports.catalog_provider import ICatalogProvider
from src.osap.ports.duplicate_resolver import IDuplicateResolver
from src.osap.ports.event_bus import IEventBus
from src.osap.ports.library_provider import ILibraryProvider
from src.osap.ports.merge_engine import IMergeEngine
from src.osap.ports.metrics import IMetricsCollector
from src.osap.ports.pipeline_engine import IPipelineEngine
from src.osap.ports.ranking_engine import IRankingEngine
from src.osap.ports.score_exporter import IScoreExporter
from src.osap.ports.score_validator import IScoreValidator
from src.osap.ports.user_profile import IUserProfileStore


class Container:
    def __init__(self) -> None:
        self._catalog_providers: list[ICatalogProvider] = []
        self._exporters: list[IScoreExporter] = []
        self._libraries: list[ILibraryProvider] = []
        self._ranking_engine: IRankingEngine | None = None
        self._ranking_config: RankingConfig = RankingConfig()
        self._validator: IScoreValidator | None = None
        self._event_bus: InMemoryEventBus | None = None
        self._metrics: InMemoryMetricsCollector | None = None
        self._cache: InMemoryCache | None = None
        self._user_profiles: InMemoryUserProfileStore | None = None
        self._job_engine: InMemoryJobEngine | None = None
        self._pipeline_engine: PipelineEngine | None = None
        self._duplicate_resolver: DuplicateResolver | None = None
        self._merge_engine: MergeEngine | None = None
        self._auth_manager: AuthenticationManager | None = None

    def register_catalog_provider(self, provider: ICatalogProvider) -> None:
        self._catalog_providers.append(provider)

    def register_exporter(self, exporter: IScoreExporter) -> None:
        self._exporters.append(exporter)

    def register_library(self, library: ILibraryProvider) -> None:
        self._libraries.append(library)

    def set_ranking_engine(self, engine: IRankingEngine) -> None:
        self._ranking_engine = engine

    def set_ranking_config(self, config: RankingConfig) -> None:
        self._ranking_config = config

    def set_validator(self, validator: IScoreValidator) -> None:
        self._validator = validator

    def set_platform(self, event_bus: InMemoryEventBus, metrics: InMemoryMetricsCollector) -> None:
        self._event_bus = event_bus
        self._metrics = metrics

    def set_cache(self, cache: InMemoryCache) -> None:
        self._cache = cache

    def set_user_profile_store(self, store: InMemoryUserProfileStore) -> None:
        self._user_profiles = store

    def set_job_engine(self, engine: InMemoryJobEngine) -> None:
        self._job_engine = engine

    def set_pipeline_engine(self, engine: PipelineEngine) -> None:
        self._pipeline_engine = engine

    def set_duplicate_resolver(self, resolver: DuplicateResolver) -> None:
        self._duplicate_resolver = resolver

    def set_merge_engine(self, engine: MergeEngine) -> None:
        self._merge_engine = engine

    def set_authentication_manager(self, manager: AuthenticationManager) -> None:
        self._auth_manager = manager

    def event_bus(self) -> IEventBus:
        if self._event_bus is None:
            raise RuntimeError("Event bus not wired")
        return self._event_bus

    def metrics(self) -> IMetricsCollector:
        if self._metrics is None:
            raise RuntimeError("Metrics not wired")
        return self._metrics

    def cache(self) -> ICache:
        if self._cache is None:
            raise RuntimeError("Cache not wired")
        return self._cache

    def user_profile_store(self) -> IUserProfileStore:
        if self._user_profiles is None:
            raise RuntimeError("User profile store not wired")
        return self._user_profiles

    def job_engine(self) -> InMemoryJobEngine:
        if self._job_engine is None:
            raise RuntimeError("Job engine not wired")
        return self._job_engine

    def pipeline_engine(self) -> IPipelineEngine:
        if self._pipeline_engine is None:
            raise RuntimeError("Pipeline engine not wired")
        return self._pipeline_engine

    def duplicate_resolver(self) -> IDuplicateResolver:
        if self._duplicate_resolver is None:
            raise RuntimeError("Duplicate resolver not wired")
        return self._duplicate_resolver

    def merge_engine(self) -> IMergeEngine:
        if self._merge_engine is None:
            raise RuntimeError("Merge engine not wired")
        return self._merge_engine

    def authentication_manager(self) -> AuthenticationManager:
        if self._auth_manager is None:
            raise RuntimeError("Authentication manager not wired")
        return self._auth_manager

    def export_manager(self) -> ExportManager:
        return ExportManager(tuple(self._exporters))

    def library_manager(self) -> LibraryManager:
        return LibraryManager(tuple(self._libraries))

    def work_resolver(self) -> WorkResolver:
        return WorkResolver()

    def work_merge_service(self) -> WorkMergeService:
        return WorkMergeService()

    def catalog_manager(self) -> CatalogManager:
        manager = CatalogManager()
        for provider in self._catalog_providers:
            manager.register(provider)
        return manager

    def work_resolution_engine(self) -> WorkResolutionEngine:
        if self._ranking_engine is None:
            raise RuntimeError("No ranking engine registered")
        orchestrator = ProviderOrchestrator(self.catalog_manager(), self._cache)
        return WorkResolutionEngine(
            self.catalog_manager(),
            self._ranking_engine,
            self.work_resolver(),
            self._ranking_config,
            self.library_manager(),
            orchestrator=orchestrator,
            evidence_engine=EvidenceEngine(),
        )
