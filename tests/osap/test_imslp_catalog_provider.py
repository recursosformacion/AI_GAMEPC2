from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.cost_level import CostLevel
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.catalogs.imslp import IMSLPCatalogProvider
from src.osap.infrastructure.mediawiki import MediaWikiClient

_SEARCH_RESPONSE: list[dict[str, object]] = [
    {
        "title": "Cançó de Comiat (Toldrà, Eduard)",
        "snippet": "Public Domain",
        "size": 1500,
        "wordcount": 200,
        "timestamp": "2024-01-01T00:00:00Z",
    }
]

_REVISIONS_RESPONSE = """
==Sources==
*File:PMLP123456-Toldra-Canco_de_Comiat.pdf
"""


class FakeMediaWikiClient(MediaWikiClient):
    def __init__(self) -> None:
        super().__init__()
        self.searches: list[str] = []
        self.downloads: list[str] = []
        self.raw_data: bytes = b"%PDF-1.4"

    def search(self, query: str, namespace: int = 0, limit: int = 10) -> list[dict[str, object]]:
        self.searches.append(query)
        if "cançó" in query.lower() or "comiat" in query.lower() or "toldrà" in query.lower():
            return _SEARCH_RESPONSE
        return []

    def page_images(self, title: str) -> list[str]:
        return ["File:test.pdf"]

    def image_info(self, file_title: str) -> dict[str, object]:
        return {
            "url": "https://imslp.org/download/test.pdf",
            "size": 50000,
            "mime": "application/pdf",
            "sha1": "abc",
        }

    def images_info_batch(self, titles: list[str]) -> list[dict[str, object]]:
        return [
            {
                "url": "https://imslp.org/download/test.pdf",
                "size": 50000,
                "mime": "application/pdf",
                "sha1": "abc",
            }
        ]

    def download(self, url: str) -> bytes:
        self.downloads.append(url)
        return self.raw_data


def _provider() -> IMSLPCatalogProvider:
    return IMSLPCatalogProvider(FakeMediaWikiClient())


class TestIMSLPSearch:
    def test_returns_candidates(self) -> None:
        candidates = _provider().search(SearchRequest(title="Cançó de Comiat", composer="Toldrà"))
        assert len(candidates) == 1
        assert candidates[0].work_descriptor.title == "Cançó de Comiat (Toldrà, Eduard)"
        assert candidates[0].work_descriptor.composer == "Eduard Toldrà"
        assert candidates[0].public_domain is True

    def test_empty_when_no_match(self) -> None:
        assert _provider().search(SearchRequest(title="Nosuchwork")) == ()

    def test_resolve_returns_first(self) -> None:
        candidate = _provider().resolve(ResolveRequest(title="Cançó de Comiat"))
        assert candidate is not None
        assert candidate.public_domain is True

    def test_download_returns_source(self) -> None:
        mw = FakeMediaWikiClient()
        provider = IMSLPCatalogProvider(mw)
        candidates = provider.search(SearchRequest(title="Cançó de Comiat"))
        acquisition = provider.download(candidates[0])
        assert isinstance(acquisition, AcquisitionResult)
        assert acquisition.source.content == b"%PDF-1.4"
        assert len(mw.downloads) == 1


def test_imslp_flows_through_orchestrator_without_special_casing() -> None:
    manager = CatalogManager()
    manager.register(IMSLPCatalogProvider(FakeMediaWikiClient()))
    orchestrator = ProviderOrchestrator(manager, cache=InMemoryCache())
    result = orchestrator.search(SearchRequest(title="Cançó de Comiat"))
    assert result.providers_used == (result.candidates[0].provider_id,)
    assert result.candidates[0].provider_id.value == "imslp"
    assert result.candidates[0].public_domain is True


class _OmrFake:
    def __init__(self) -> None:
        self.hits = 0

    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("omr")

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            cost_level=CostLevel.EXPENSIVE,
            formats=(OutputFormat.MUSICXML,),
        )

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        self.hits += 1
        work = WorkDescriptor(work_id=WorkId("omr"), title="Cançó de Comiat", composer="Toldrà")
        return (
            CandidateRepresentation(
                candidate_id=CandidateId("omr-1"),
                work_descriptor=work,
                provider_id=self.provider_id,
                format=OutputFormat.MUSICXML,
            ),
        )

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        return None

    def download(self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None) -> object:
        raise NotImplementedError


def test_omr_and_imslp_coexist_without_special_casing() -> None:
    manager = CatalogManager()
    manager.register(IMSLPCatalogProvider(FakeMediaWikiClient()))
    omr = _OmrFake()
    manager.register(omr)
    orchestrator = ProviderOrchestrator(manager, cache=InMemoryCache())

    plain = orchestrator.search(SearchRequest(title="Cançó de Comiat"))
    assert {c.provider_id.value for c in plain.candidates} == {"imslp"}
    assert omr.hits == 0  # FREE IMSLP satisface; OMR (caro) no se consulta

    json_query = orchestrator.search(SearchRequest(title="Cançó de Comiat", desired_format=OutputFormat.JSON))
    assert {c.provider_id.value for c in json_query.candidates} == {"imslp", "omr"}
    assert omr.hits == 1  # IMSLP no ofrece JSON -> continúa a OMR
