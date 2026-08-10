"""V3.2 — OpenAPI generation tests.

OpenAPI is a generated artifact (ADR-0029): it derives from the public DTOs and REST
routes, is never hand-edited, and is deterministic. These tests are the "canary" that
nobody breaks the public contract without noticing.
"""

from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
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
    CatalogId,
    Confidence,
    Duration,
    ProviderId,
    SourceId,
)
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.infrastructure.jobs import InMemoryJobEngine
from src.osap.infrastructure.metrics import InMemoryMetricsCollector
from src.osap.infrastructure.user_profile import InMemoryUserProfileStore
from src.osap.ports.catalog_provider import ICatalogProvider
from src.osap.ports.ranking_engine import IRankingEngine


class _FakeCatalog(ICatalogProvider):
    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("fake")

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        return ()

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


class _FakeRanking(IRankingEngine):
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
    container.register_catalog_provider(_FakeCatalog())
    container.set_ranking_engine(_FakeRanking())
    container.set_ranking_config(RankingConfig())
    bus = InMemoryEventBus()
    container.set_platform(bus, InMemoryMetricsCollector())
    container.set_job_engine(InMemoryJobEngine(bus))
    container.set_user_profile_store(InMemoryUserProfileStore())
    return container


def _spec() -> dict[str, object]:
    client = TestClient(create_platform_app(_container()))
    spec = client.get("/openapi.json").json()
    assert isinstance(spec, dict)
    return spec


_PUBLIC_DTOS = {
    "SearchRequest",
    "SearchResponse",
    "JobResponse",
    "ProviderResponse",
    "KnowledgeObservationDTO",
    "KnowledgeFactDTO",
    "KnowledgeSuggestionDTO",
    "SystemHealthResponse",
    "SystemVersionResponse",
    "SystemStatisticsResponse",
    "ErrorEnvelope",
}

_PATHS = {
    "/api/v1/searches",
    "/api/v1/searches/{search_id}",
    "/api/v1/jobs",
    "/api/v1/jobs/{job_id}",
    "/api/v1/providers",
    "/api/v1/providers/{provider_id}",
    "/api/v1/providers/{provider_id}/status",
    "/api/v1/knowledge/observations",
    "/api/v1/knowledge/facts",
    "/api/v1/knowledge/suggestions",
    "/api/v1/system/health",
    "/api/v1/system/ready",
    "/api/v1/system/live",
    "/api/v1/system/version",
    "/api/v1/system/statistics",
}

_FORBIDDEN = ("matcher", "ranking", "mergeengine", "evidence", "knowledgecollector", "knowledgemin")


def test_openapi_json_exists() -> None:
    client = TestClient(create_platform_app(_container()))
    assert client.get("/openapi.json").status_code == 200


def test_docs_exists() -> None:
    client = TestClient(create_platform_app(_container()))
    assert client.get("/docs").status_code == 200


def test_redoc_exists() -> None:
    client = TestClient(create_platform_app(_container()))
    assert client.get("/redoc").status_code == 200


def test_spec_is_openapi_3_1() -> None:
    spec = _spec()
    assert spec["openapi"].startswith("3.1")


def test_metadata_complete() -> None:
    spec = _spec()
    info = spec["info"]
    assert isinstance(info, dict)
    assert info["title"]
    assert info["description"]
    assert info["version"]
    assert "license" in info and info["license"]["name"]
    assert "contact" in info


def test_all_public_dtos_present() -> None:
    spec = _spec()
    schemas = spec["components"]["schemas"]
    assert isinstance(schemas, dict)
    assert set(schemas) >= _PUBLIC_DTOS
    assert any(name.startswith("SuccessEnvelope") for name in schemas)


def test_all_endpoints_present() -> None:
    spec = _spec()
    assert set(spec["paths"]) >= _PATHS


def test_five_tags_grouped() -> None:
    spec = _spec()
    assert isinstance(spec["paths"], dict)
    tags = {
        operation.get("tags", [None])[0]
        for path in spec["paths"].values()
        if isinstance(path, dict)
        for operation in path.values()
        if isinstance(operation, dict)
    }
    assert tags == {"Searches", "Jobs", "Providers", "Knowledge", "Votes", "Composers", "System", "Auth", "Sources"}


def test_examples_in_all_endpoints() -> None:
    spec = _spec()
    for path, item in spec["paths"].items():
        assert isinstance(item, dict)
        for operation in item.values():
            if not isinstance(operation, dict) or operation.get("parameters"):
                continue
            responses = operation.get("responses")
            assert isinstance(responses, dict), f"{path} has no documented responses"
            assert any(
                isinstance(content, dict)
                for resp in responses.values()
                if isinstance(resp, dict)
                and isinstance((content := resp.get("content")), dict)
            ), f"{path} {operation.get('summary')} has no response example"


def test_internal_components_not_documented() -> None:
    spec = _spec()
    paths = str(list(spec["paths"].keys())).lower()
    schema_names = {str(name).lower() for name in spec["components"]["schemas"]}
    for forbidden in _FORBIDDEN:
        assert forbidden not in paths, f"internal component leaked in paths: {forbidden}"
        assert forbidden not in schema_names, f"internal component leaked as a schema: {forbidden}"


def test_request_id_in_examples() -> None:
    spec = _spec()
    serialized = str(spec)
    assert "request_id" in serialized


def test_validates_with_standard_validator() -> None:
    from openapi_spec_validator import validate

    spec = _spec()
    validate(spec)


def test_generation_is_deterministic() -> None:
    assert _spec() == _spec()
