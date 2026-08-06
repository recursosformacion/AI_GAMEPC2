"""V3.1 — OSAP Platform API tests (HTTP integration + contract)."""

from fastapi.testclient import TestClient

from src.osap.api.platform import KnowledgeStore
from src.osap.api.platform_app import create_platform_app
from src.osap.bootstrap.container import Container
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.knowledge import (
    KnowledgeBase,
    KnowledgeFact,
    KnowledgeFactType,
    KnowledgeObservation,
    KnowledgeSource,
    KnowledgeSuggestion,
    KnowledgeSuggestionType,
)
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
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.infrastructure.jobs import InMemoryJobEngine
from src.osap.infrastructure.metrics import InMemoryMetricsCollector
from src.osap.infrastructure.user_profile import InMemoryUserProfileStore
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
        return tuple(ScoreRanking(c, 1.0, {"score": 1.0}) for c in candidates)


def _container() -> Container:
    container = Container()
    container.register_catalog_provider(FakeCatalog())
    container.set_ranking_engine(FakeRanking())
    container.set_ranking_config(RankingConfig())
    bus = InMemoryEventBus()
    container.set_platform(bus, InMemoryMetricsCollector())
    container.set_job_engine(InMemoryJobEngine(bus))
    container.set_user_profile_store(InMemoryUserProfileStore())
    return container


def _knowledge_store() -> KnowledgeStore:
    base = KnowledgeBase(
        observations=(
            KnowledgeObservation(
                execution_id="e1", source=KnowledgeSource.MERGE, field="title", value="Ave Verum K618"
            ),
        ),
        facts=(KnowledgeFact(fact_type=KnowledgeFactType.FREQUENCY, field="title", value="Ave Verum K618", count=2),),
        suggestions=(
            KnowledgeSuggestion(
                suggestion_type=KnowledgeSuggestionType.ADD_ALIAS,
                field="title",
                source_value="Ave Verum K618",
                target_value="Ave Verum Corpus KV 618",
                reason="observed 2 times",
            ),
        ),
    )
    return KnowledgeStore(base)


def _client(knowledge: KnowledgeStore | None = None) -> TestClient:
    return TestClient(create_platform_app(_container(), knowledge))


# --- envelope / request_id --------------------------------------------------


def test_every_response_has_request_id() -> None:
    client = _client()
    for path in (
        "/api/v1/providers",
        "/api/v1/jobs",
        "/api/v1/knowledge/facts",
        "/api/v1/system/health",
    ):
        body = client.get(path).json()
        assert body["success"] is True
        assert body["request_id"]


def test_error_response_is_uniform() -> None:
    client = _client()
    resp = client.post("/api/v1/searches", json={"query": "   "})
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["request_id"]
    assert body["error"]["code"] == "INVALID_QUERY"
    assert "details" in body["error"]


# --- search -----------------------------------------------------------------


def test_search_creates_resource_and_returns_201() -> None:
    client = _client()
    resp = client.post("/api/v1/searches", json={"query": "Ave Verum", "limit": 5})
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    location = resp.headers["location"]
    search_id = body["data"]["search_id"]
    assert location == f"/api/v1/searches/{search_id}"
    assert len(body["data"]["results"]) == 1
    result = body["data"]["results"][0]
    assert result["work"]["title"] == "Ave Verum Corpus"
    assert result["representation"]["provider"] == "fake"
    assert result["representation"]["format"] == "musicxml"
    assert "evidence" in result


def test_search_can_be_retrieved_by_id() -> None:
    client = _client()
    created = client.post("/api/v1/searches", json={"query": "Ave Verum"}).json()
    search_id = created["data"]["search_id"]
    resp = client.get(f"/api/v1/searches/{search_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["search_id"] == search_id


def test_search_missing_returns_404() -> None:
    client = _client()
    resp = client.get("/api/v1/searches/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --- jobs -------------------------------------------------------------------


def test_create_and_list_and_get_job() -> None:
    client = _client()
    created = client.post("/api/v1/jobs", json={"type": "provider-sync"})
    assert created.status_code == 201
    job = created.json()["data"]
    assert job["type"] == "provider-sync"
    assert job["state"] == "completed"
    assert created.headers["location"] == f"/api/v1/jobs/{job['job_id']}"

    jobs = client.get("/api/v1/jobs").json()["data"]
    assert [j["job_id"] for j in jobs] == [job["job_id"]]

    got = client.get(f"/api/v1/jobs/{job['job_id']}").json()["data"]
    assert got["job_id"] == job["job_id"]


def test_job_missing_returns_404() -> None:
    client = _client()
    resp = client.get("/api/v1/jobs/unknown")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --- providers --------------------------------------------------------------


def test_list_and_get_provider() -> None:
    client = _client()
    providers = client.get("/api/v1/providers").json()["data"]
    assert [p["provider_id"] for p in providers] == ["fake"]
    assert providers[0]["name"] == "Fake"

    detail = client.get("/api/v1/providers/fake").json()["data"]
    assert detail["provider_id"] == "fake"

    status = client.get("/api/v1/providers/fake/status").json()["data"]
    assert status["available"] is True


def test_provider_missing_returns_404() -> None:
    client = _client()
    assert client.get("/api/v1/providers/nope").status_code == 404
    assert client.get("/api/v1/providers/nope/status").status_code == 404


# --- knowledge --------------------------------------------------------------


def test_knowledge_read_only_endpoints() -> None:
    client = _client(_knowledge_store())
    obs = client.get("/api/v1/knowledge/observations").json()["data"]
    facts = client.get("/api/v1/knowledge/facts").json()["data"]
    suggestions = client.get("/api/v1/knowledge/suggestions").json()["data"]
    assert len(obs) == 1
    assert obs[0]["source"] == "merge"
    assert facts[0]["count"] == 2
    assert suggestions[0]["suggestion_type"] == "add_alias"


def test_knowledge_empty_by_default() -> None:
    client = _client()
    assert client.get("/api/v1/knowledge/facts").json()["data"] == []


# --- system -----------------------------------------------------------------


def test_system_endpoints() -> None:
    client = _client(_knowledge_store())
    assert client.get("/api/v1/system/health").json()["data"]["status"] == "ok"
    assert client.get("/api/v1/system/ready").json()["data"]["status"] == "ready"
    assert client.get("/api/v1/system/live").json()["data"]["status"] == "live"
    assert client.get("/api/v1/system/version").json()["data"]["version"]

    stats = client.get("/api/v1/system/statistics").json()["data"]
    assert stats["providers"] == 1
    assert stats["knowledge_observations"] == 1
    assert stats["searches"] == 0


# --- OpenAPI ----------------------------------------------------------------


def test_openapi_generated_automatically() -> None:
    client = _client()
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/api/v1/searches" in paths
    assert "/api/v1/searches/{search_id}" in paths
    assert "/api/v1/jobs" in paths
    assert "/api/v1/knowledge/observations" in paths
    assert "/api/v1/system/health" in paths
    assert spec["info"]["title"] == "OSAP Platform API"
