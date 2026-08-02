import pytest
from fastapi.testclient import TestClient

from src.osap.api.app import create_app
from src.osap.bootstrap.container import Container
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.score_ranking import ScoreRanking
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    Duration,
    ProviderId,
    SourceId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.catalog_provider import ICatalogProvider
from src.osap.ports.ranking_engine import IRankingEngine


class FakeCatalog(ICatalogProvider):
    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("fake")

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        return (
            CandidateRepresentation(
                candidate_id=CandidateId("c1"),
                work_descriptor=WorkDescriptor(WorkId("w1"), "Ave Verum Corpus", "Wolfgang Amadeus Mozart"),
                provider_id=self.provider_id,
                format=OutputFormat.MUSICXML,
                confidence=Confidence(0.9),
                public_domain=True,
                metadata={"genres": "Motet"},
            ),
        )

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        return None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        return AcquisitionResult(
            provider_id=self.provider_id,
            source=MusicalSource(SourceId("s1"), b"%PDF", OutputFormat.MUSICXML),
            confidence=Confidence(1.0),
            processing_time=Duration(0.0),
            format=OutputFormat.MUSICXML,
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(CatalogId("fake"), "Fake", self.provider_id, "local", CatalogStatus.AVAILABLE)

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(self.provider_id, formats=(OutputFormat.MUSICXML,))


class FakeRanking(IRankingEngine):
    def rank(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        request: ResolveRequest,
        config: RankingConfig,
    ) -> tuple[CandidateRepresentation, ...]:
        return candidates

    def rank_detailed(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        request: ResolveRequest,
        config: RankingConfig,
    ) -> tuple[ScoreRanking, ...]:
        from src.osap.domain.score_ranking import ScoreRanking

        return tuple(ScoreRanking(c, 1.0, {"score": 1.0}) for c in candidates)


def _container() -> Container:
    from src.osap.domain.dataset_descriptor import DatasetDescriptor
    from src.osap.domain.value_objects import DatasetId
    from src.osap.infrastructure.datasets import InMemoryDatasetRegistry
    from src.osap.infrastructure.datasets.dataset_installer import IDatasetInstaller, ProgressCallback
    from src.osap.infrastructure.datasets.dataset_manager import DatasetManager
    from src.osap.infrastructure.datasets.dataset_settings import DatasetSettings
    from src.osap.infrastructure.events import InMemoryEventBus
    from src.osap.infrastructure.jobs import InMemoryJobEngine
    from src.osap.infrastructure.metrics import InMemoryMetricsCollector
    from src.osap.infrastructure.user_profile import InMemoryUserProfileStore

    class _FakeInstaller(IDatasetInstaller):
        def install(self, d: DatasetDescriptor, s: DatasetSettings, p: ProgressCallback) -> None:  # noqa: ARG002
            pass

        def update(self, d: DatasetDescriptor, s: DatasetSettings, p: ProgressCallback) -> None:  # noqa: ARG002
            pass

        def remove(self, did: DatasetId, s: DatasetSettings) -> None:  # noqa: ARG002
            pass

        def verify(self, d: DatasetDescriptor, s: DatasetSettings) -> bool:  # noqa: ARG002
            return False

        def location(self, did: DatasetId, s: DatasetSettings) -> str | None:  # noqa: ARG002
            return None

    container = Container()
    container.register_catalog_provider(FakeCatalog())
    container.set_ranking_engine(FakeRanking())
    container.set_ranking_config(RankingConfig())
    bus = InMemoryEventBus()
    container.set_platform(bus, InMemoryMetricsCollector())
    container.set_job_engine(InMemoryJobEngine(bus))
    container.set_user_profile_store(InMemoryUserProfileStore())
    registry = InMemoryDatasetRegistry()
    registry.register(
        DatasetDescriptor(
            dataset_id=DatasetId("pdmx"),
            name="PDMX",
            hf_path="openmusic/pdmx",
            expected_size_bytes=1,
            license="Public Domain",
        )
    )
    container.set_dataset_manager(DatasetManager(registry, _FakeInstaller(), DatasetSettings(cache_dir=None)))
    return container


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(_container()))


class TestApi:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_providers(self, client: TestClient) -> None:
        resp = client.get("/api/v1/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert any(p["provider"] == "fake" for p in data)
        assert "status" in data[0]
        assert data[0]["available"] is True

    def test_search(self, client: TestClient) -> None:
        resp = client.get("/api/v1/search", params={"query": "Ave Verum"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["works"] == 1
        assert data["items"][0]["title"] == "Ave Verum Corpus"
        assert data["items"][0]["display_title"] == "Ave Verum Corpus"
        assert data["items"][0]["canonical_key"]
        assert data["items"][0]["public_domain"] is True

    def test_preview(self, client: TestClient) -> None:
        resp = client.post("/api/v1/preview", json={"query": "Ave Verum"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["work"] == "Ave Verum Corpus"
        assert data["representations"][0]["format"] == "musicxml"

    def test_resolve_returns_job(self, client: TestClient) -> None:
        resp = client.post("/api/v1/resolve", json={"query": "Ave Verum"})
        assert resp.status_code == 200
        job = resp.json()
        assert job["type"] == "resolve"
        assert job["state"] in ("pending", "running", "completed", "failed")

    def test_jobs_list(self, client: TestClient) -> None:
        client.post("/api/v1/resolve", json={"query": "Ave Verum"})
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_library_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/library")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_datasets_lists_pdmx(self, client: TestClient) -> None:
        resp = client.get("/api/v1/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert any(d["dataset_id"] == "pdmx" for d in data)
        assert data[0]["status"] in ("not_present", "ready", "downloading", "streaming", "error")

    def test_settings(self, client: TestClient) -> None:
        resp = client.get("/api/v1/settings")
        assert resp.status_code == 200
        body = resp.json()
        assert "library_root" in body
        assert "default_output_format" in body

    def test_users_list(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_user_detail_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/nobody")
        assert resp.status_code == 404

    def test_websocket_route_registered(self) -> None:
        from src.osap.api.app import create_app

        app = create_app(_container())
        assert any(getattr(r, "path", None) == "/api/v1/events/ws" for r in app.routes)


def test_websocket_delivers_events() -> None:
    from src.osap.domain.event import Event
    from src.osap.infrastructure.events import InMemoryEventBus
    from src.osap.infrastructure.jobs import InMemoryJobEngine
    from src.osap.infrastructure.metrics import InMemoryMetricsCollector

    container = Container()
    container.register_catalog_provider(FakeCatalog())
    container.set_ranking_engine(FakeRanking())
    container.set_ranking_config(RankingConfig())
    bus = InMemoryEventBus()
    container.set_platform(bus, InMemoryMetricsCollector())
    container.set_job_engine(InMemoryJobEngine(bus))
    app = create_app(container)

    with TestClient(app) as client, client.websocket_connect("/api/v1/events/ws") as ws:
        bus.publish(
            Event(
                event_type="JobStarted",
                aggregate_id="job-1",
                payload={"state": "running", "progress": 10},
            )
        )
        data = ws.receive_json()
        assert data["event_type"] == "JobStarted"
        assert data["payload"]["state"] == "running"


def test_events_sse_endpoint_and_bus_delivery() -> None:
    from src.osap.api.app import create_app
    from src.osap.domain.event import Event
    from src.osap.infrastructure.events import InMemoryEventBus
    from src.osap.infrastructure.jobs import InMemoryJobEngine
    from src.osap.infrastructure.metrics import InMemoryMetricsCollector

    container = Container()
    container.register_catalog_provider(FakeCatalog())
    container.set_ranking_engine(FakeRanking())
    container.set_ranking_config(RankingConfig())
    bus = InMemoryEventBus()
    container.set_platform(bus, InMemoryMetricsCollector())
    container.set_job_engine(InMemoryJobEngine(bus))
    app = create_app(container)

    # The /events SSE route is registered.
    assert any(getattr(r, "path", None) == "/api/v1/events" for r in app.routes)

    # The EventBus delivers to "*" subscribers (the mechanism /events relies on).
    received: list[str] = []
    bus.subscribe("*", lambda e: received.append(e.event_type))
    bus.publish(Event(event_type="JobStarted", aggregate_id="job-1", payload={"progress": 10}))
    assert "JobStarted" in received
