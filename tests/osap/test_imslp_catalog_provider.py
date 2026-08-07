from pathlib import Path

from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import ProviderId
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.catalogs.remote.remote_catalog_provider import RemoteCatalogProvider
from src.osap.infrastructure.mediawiki import MediaWikiClient
from src.osap.infrastructure.providers.fetchers import MediaWikiFetcher

_SEARCH_RESPONSE: list[dict[str, object]] = [
    {
        "title": "Cançó de Comiat (Toldrà, Eduard)",
        "snippet": "Public Domain",
        "size": 1500,
        "wordcount": 200,
        "timestamp": "2024-01-01T00:00:00Z",
    }
]


class FakeMediaWikiClient(MediaWikiClient):
    def __init__(self) -> None:
        super().__init__()
        self.searches: list[str] = []

    def search(self, query: str, namespace: int = 0, limit: int = 10) -> list[dict[str, object]]:
        self.searches.append(query)
        if "cançó" in query.lower() or "comiat" in query.lower() or "toldrà" in query.lower():
            return _SEARCH_RESPONSE
        return []


DEF_PATH = Path(__file__).resolve().parents[2] / "providers" / "imslp"


def _provider() -> tuple[RemoteCatalogProvider, FakeMediaWikiClient]:
    mw = FakeMediaWikiClient()
    fetcher = MediaWikiFetcher(mw)
    provider = RemoteCatalogProvider(definition_path=DEF_PATH, fetcher=fetcher)
    return provider, mw


class TestIMSLPSearch:
    def test_returns_candidates(self) -> None:
        provider, _ = _provider()
        candidates = provider.search(SearchRequest(title="Cançó de Comiat", composer="Toldrà"))
        assert len(candidates) == 1
        assert candidates[0].work_descriptor.title == "Cançó de Comiat (Toldrà, Eduard)"
        assert candidates[0].work_descriptor.composer == "Eduard Toldrà"
        assert candidates[0].public_domain is True

    def test_empty_when_no_match(self) -> None:
        provider, _ = _provider()
        assert provider.search(SearchRequest(title="Nosuchwork")) == ()

    def test_resolve_returns_first(self) -> None:
        provider, _ = _provider()
        candidate = provider.resolve(ResolveRequest(title="Cançó de Comiat"))
        assert candidate is not None
        assert candidate.public_domain is True


def test_imslp_flows_through_orchestrator_without_special_casing() -> None:
    manager = CatalogManager()
    provider, _ = _provider()
    manager.register(provider)
    orchestrator = ProviderOrchestrator(manager, cache=InMemoryCache())
    result = orchestrator.search(SearchRequest(title="Cançó de Comiat"))
    assert result.candidates[0].provider_id.value == "imslp"
    assert result.candidates[0].public_domain is True


class _OmrFake:
    def __init__(self) -> None:
        self.hits = 0
        self._provider_id = ProviderId("omr")

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(provider_id=self._provider_id, formats=(OutputFormat.MUSICXML,))

    def search(self, request: SearchRequest):
        self.hits += 1
        return ()


def test_omr_and_imslp_coexist_without_special_casing() -> None:
    manager = CatalogManager()
    provider, _ = _provider()
    manager.register(provider)
    omr = _OmrFake()
    manager.register(omr)
    orchestrator = ProviderOrchestrator(manager, cache=InMemoryCache())

    plain = orchestrator.search(SearchRequest(title="Cançó de Comiat"))
    assert {c.provider_id.value for c in plain.candidates} == {"imslp"}
    assert omr.hits == 1
