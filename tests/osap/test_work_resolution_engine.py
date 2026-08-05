from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.work_resolution_engine import WorkResolutionEngine
from src.osap.application.work_resolver import WorkResolver
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.dataset_descriptor import DatasetDescriptor
from src.osap.domain.dataset_status import DatasetStatus
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.resolve_result import ResolveResult
from src.osap.domain.resource import Resource, ResourceKind, ResourceStatus
from src.osap.domain.score_ranking import ScoreRanking
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    DatasetId,
    Duration,
    ProviderId,
    ResourceId,
    SourceId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.datasets.dataset_installer import IDatasetInstaller, ProgressCallback
from src.osap.infrastructure.datasets.dataset_registry import IDatasetRegistry
from src.osap.infrastructure.resources.resource_provider import IResourceProvider
from src.osap.ports.catalog_provider import ICatalogProvider
from src.osap.ports.ranking_engine import IRankingEngine


def _not_present_pdmx() -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=DatasetId("pdmx"),
        name="PDMX",
        hf_path="pnlong/PDMX",
        status=DatasetStatus.NOT_PRESENT,
    )


class _FakeInstaller(IDatasetInstaller):
    def install(self, descriptor: DatasetDescriptor, settings: object, on_progress: ProgressCallback) -> None:
        pass

    def update(self, descriptor: DatasetDescriptor, settings: object, on_progress: ProgressCallback) -> None:
        pass

    def remove(self, dataset_id: DatasetId, settings: object) -> None:
        pass

    def verify(self, descriptor: DatasetDescriptor, settings: object) -> bool:
        return True

    def location(self, dataset_id: DatasetId, settings: object) -> str | None:
        return None


class FakeDatasetRegistry(IDatasetRegistry):
    def all(self) -> tuple[DatasetDescriptor, ...]:
        return ()

    def find(self, dataset_id: DatasetId) -> DatasetDescriptor | None:
        return _not_present_pdmx()

    def update_status(self, dataset_id: DatasetId, status: DatasetStatus) -> None:
        pass

    def register(self, descriptor: DatasetDescriptor) -> None:
        pass


class FakeResourceProvider(IResourceProvider):
    def __init__(self, resource_id: str) -> None:
        self._id = resource_id
        self._installed = True

    @property
    def resource_id(self) -> str:
        return self._id

    def install(self, index_only: bool = False) -> None:
        self._installed = True

    def update(self) -> None:
        pass

    def remove(self) -> None:
        self._installed = False

    def exists(self) -> bool:
        return self._installed

    def status(self) -> ResourceStatus:
        return ResourceStatus.INSTALLED if self._installed else ResourceStatus.NOT_INSTALLED

    def metadata(self) -> Resource:
        return Resource(
            resource_id=ResourceId(self._id),
            name=self._id,
            kind=ResourceKind.DATASET,
            provider=ProviderId("test"),
            status=self.status(),
        )


class FakeCatalog(ICatalogProvider):
    def __init__(self, provider_id: str, candidate: CandidateRepresentation | None) -> None:
        self._provider_id = ProviderId(provider_id)
        self._candidate = candidate
        self.downloaded = False

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def required_resources(self) -> tuple[str, ...]:
        return ("pdmx",) if self._provider_id.value == "pdmx" else ()

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        return (self._candidate,) if self._candidate else ()

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        return self._candidate

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        self.downloaded = True
        return AcquisitionResult(
            provider_id=self._provider_id,
            source=MusicalSource(SourceId("s1"), b"%PDF", OutputFormat.MUSICXML),
            confidence=Confidence(1.0),
            processing_time=Duration(0.0),
            format=OutputFormat.MUSICXML,
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId(self._provider_id.value),
            name=self._provider_id.value,
            provider_id=self._provider_id,
            source="x",
            status=CatalogStatus.INSTALLED,
        )

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(provider_id=self._provider_id, formats=(OutputFormat.MUSICXML,), offline=True)


class FakeRanking(IRankingEngine):
    def rank(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        request: ResolveRequest,
        config: RankingConfig,
    ) -> tuple[CandidateRepresentation, ...]:
        return tuple(sorted(candidates, key=lambda c: c.confidence.value, reverse=True))

    def rank_detailed(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        request: ResolveRequest,
        config: RankingConfig,
    ) -> tuple[ScoreRanking, ...]:
        return tuple(
            ScoreRanking(candidate=c, total=c.confidence.value, details={"score": c.confidence.value}, reason="test")
            for c in candidates
        )


def _candidate(cid: str, confidence: float) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=WorkDescriptor(work_id=WorkId(cid), title="Canço de Comiat"),
        provider_id=ProviderId("imslp"),
        format=OutputFormat.MUSICXML,
        confidence=Confidence(confidence),
    )


def _engine(catalog: FakeCatalog) -> WorkResolutionEngine:
    manager = CatalogManager()
    manager.register(catalog)
    return WorkResolutionEngine(
        catalog_manager=manager,
        ranking_engine=FakeRanking(),
        work_resolver=WorkResolver(),
        config=RankingConfig(),
    )


class TestWorkResolutionEngine:
    def test_resolve_returns_best_candidate(self) -> None:
        catalog = FakeCatalog("imslp", _candidate("c1", 0.9))
        result = _engine(catalog).resolve(ResolveRequest(title="Canço de Comiat"))
        assert isinstance(result, ResolveResult)
        assert result.chosen is not None
        assert result.chosen.candidate_id == CandidateId("c1")

    def test_resolve_no_candidates(self) -> None:
        catalog = FakeCatalog("imslp", None)
        result = _engine(catalog).resolve(ResolveRequest(title="Canço de Comiat"))
        assert result.chosen is None

    def test_resolve_with_download(self) -> None:
        catalog = FakeCatalog("imslp", _candidate("c1", 0.9))
        result = _engine(catalog).resolve(ResolveRequest(title="Canço de Comiat"), download=True)
        assert catalog.downloaded is True
        assert result.chosen is not None

    def test_progress_callback_reports_provider_activity(self) -> None:
        catalog = FakeCatalog("imslp", _candidate("c1", 0.9))
        messages: list[str] = []
        engine = _engine(catalog)
        engine.rank(ResolveRequest(title="Canço de Comiat"), on_progress=messages.append)
        assert any("Consultando imslp" in m for m in messages)
        assert any("candidato" in m for m in messages)

    def test_resolve_progress_reports_download(self) -> None:
        catalog = FakeCatalog("imslp", _candidate("c1", 0.9))
        messages: list[str] = []
        engine = _engine(catalog)
        engine.resolve(ResolveRequest(title="Canço de Comiat"), download=True, on_progress=messages.append)
        assert any("Descargando imslp" in m for m in messages)

    def test_resolve_scoped_to_given_representations(self) -> None:
        # When representations are supplied, resolution only considers them: it
        # must NOT re-scan other providers (even if they would return more).
        manual = CandidateRepresentation(
            candidate_id=CandidateId("m1"),
            work_descriptor=WorkDescriptor(work_id=WorkId("w"), title="Ave Verum Corpus", composer="Mozart"),
            provider_id=ProviderId("imslp"),
            format=OutputFormat.PDF,
            downloadable=False,
            manual_download=True,
            download_url="https://imslp.org/wiki/Ave_Verum_Corpus",
            notes="anti-bot",
        )
        messages: list[str] = []
        result = _engine(FakeCatalog("imslp", None)).resolve(
            ResolveRequest(title="Ave Verum Corpus"),
            download=True,
            representations=(manual,),
            on_progress=messages.append,
        )
        assert result.chosen is not None
        assert result.chosen.manual_download is True
        assert result.chosen.download_url == "https://imslp.org/wiki/Ave_Verum_Corpus"
        assert result.local_path is None
        assert all("pdmx" not in m and "openscore" not in m for m in messages)
        assert any("descarga manual" in m for m in messages)

    def test_resource_diagnostics_when_required(self) -> None:
        catalog = FakeCatalog("pdmx", _candidate("c1", 0.9))
        result = _engine(catalog).resolve(ResolveRequest(title="Canço de Comiat"))
        assert result.chosen is not None
        assert catalog.downloaded is False


class _UnavailableCatalog(FakeCatalog):
    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        from src.osap.domain.errors import ResourceUnavailableError

        raise ResourceUnavailableError("source unavailable")


class TestProviderUnavailable:
    def test_unavailable_provider_is_reported_and_resolution_continues(self) -> None:
        working = FakeCatalog("imslp", _candidate("c1", 0.9))
        unavailable = _UnavailableCatalog("pdmx", None)
        catalog_manager = CatalogManager()
        catalog_manager.register(unavailable)
        catalog_manager.register(working)

        engine = WorkResolutionEngine(
            catalog_manager=catalog_manager,
            ranking_engine=FakeRanking(),
            work_resolver=WorkResolver(),
            config=RankingConfig(),
        )
        request = ResolveRequest(title="Canço de Comiat")
        reports = engine.provider_status(request)
        by_provider = {r.provider_id.value: r for r in reports}
        assert by_provider["pdmx"].outcome == "unavailable"
        assert by_provider["imslp"].outcome == "ok"

        result = engine.resolve(request)
        assert result.chosen is not None
        assert result.chosen.provider_id.value == "imslp"
