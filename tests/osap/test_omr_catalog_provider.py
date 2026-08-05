from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.domain.cost_level import CostLevel
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.catalogs import OmrCatalogProvider

BASE = "https://repository.org"
SEARCH_PAYLOAD = {
    "total": 1,
    "resources": [
        {
            "id": "res_abc123",
            "title": "Ave Verum Corpus",
            "provider_id": "omr-v3",
            "composer": "Wolfgang Amadeus Mozart",
            "catalog": "K. 618",
            "type": "score",
            "formats": ["xml", "pdf"],
            "access": {
                "mode": "direct",
                "license": "CC0-1.0",
                "url": f"{BASE}/scores/ave-verum.xml",
                "expires": "2025-01-01T00:00:00Z",
            },
        }
    ],
}


class FakeHttp:
    def __init__(self, payload: object = SEARCH_PAYLOAD, content: bytes = b"<score/>") -> None:
        self._payload = payload
        self._content = content
        self.calls: list[tuple[str, dict[str, str]]] = []

    def build_url(self, base_url: str, path: str, params: dict[str, str]) -> str:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}{path}?{query}"

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> object:
        self.calls.append((url, headers or {}))
        return self._payload

    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        self.calls.append((url, headers or {}))
        return self._content


def _provider(payload: object = SEARCH_PAYLOAD) -> tuple[OmrCatalogProvider, FakeHttp]:
    http = FakeHttp(payload)
    return OmrCatalogProvider(http, BASE, api_key="secret"), http


def test_search_maps_resources_to_candidates() -> None:
    provider, http = _provider()
    candidates = provider.search(SearchRequest(composer="Mozart", title="Ave Verum"))
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.provider_id.value == "omr"
    assert candidate.remote_id == "res_abc123"
    assert candidate.format is OutputFormat.MUSICXML
    assert candidate.work_descriptor.title == "Ave Verum Corpus"
    assert candidate.work_descriptor.composer == "Wolfgang Amadeus Mozart"
    assert candidate.work_descriptor.catalogue_number == "K. 618"
    assert candidate.download_url == f"{BASE}/scores/ave-verum.xml"
    assert candidate.public_domain is True
    assert candidate.downloadable is True


def test_search_sends_api_key_and_accept_headers() -> None:
    provider, http = _provider()
    provider.search(SearchRequest(composer="Mozart"))
    _, headers = http.calls[0]
    assert headers["X-API-Key"] == "secret"
    assert headers["Accept"] == "application/vnd.osap-api.v1.2+json"


def test_capabilities_are_expensive() -> None:
    provider, _ = _provider()
    caps = provider.capabilities()
    assert caps.cost_level is CostLevel.EXPENSIVE
    assert caps.supports_composer is True
    assert caps.supports_catalogue is True
    assert OutputFormat.MUSICXML in caps.formats


def test_resolve_returns_first_candidate() -> None:
    provider, _ = _provider()
    result = provider.resolve(ResolveRequest(title="Ave Verum"))
    assert result is not None
    assert result.remote_id == "res_abc123"


def test_download_returns_acquisition() -> None:
    provider, http = _provider()
    candidate = provider.search(SearchRequest(title="Ave Verum"))[0]
    acquisition = provider.download(candidate)
    assert acquisition.provider_id.value == "omr"
    assert acquisition.source.content == b"<score/>"
    assert acquisition.format is OutputFormat.MUSICXML
    assert http.calls[-1][0] == candidate.download_url


def test_flows_through_orchestrator_without_special_casing() -> None:
    provider, _ = _provider()
    manager = CatalogManager()
    manager.register(provider)
    orchestrator = ProviderOrchestrator(manager, cache=InMemoryCache())
    result = orchestrator.search(SearchRequest(composer="Mozart"))
    assert result.providers_used == (provider.provider_id,)
    assert len(result.candidates) == 1
    assert result.candidates[0].provider_id.value == "omr"
