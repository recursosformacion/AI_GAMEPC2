from pathlib import Path

from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
from src.osap.infrastructure.catalogs.remote.remote_catalog_provider import RemoteCatalogProvider
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderHttpClient

BASE = "https://repository.org"
SEARCH_PAYLOAD: dict[str, object] = {
    "works": [
        {
            "id": "w1",
            "title": "Ave Verum Corpus",
            "composer": "Wolfgang Amadeus Mozart",
            "catalogue": "K. 618",
            "metadata": {
                "subtitle": "Motet",
                "license": "CC0-1.0",
                "public_domain": True,
                "genres": ["motet"],
            },
            "statistics": {"favorites": 12, "downloads": 340, "views": 900, "rating": 4.5},
            "resources": [
                {
                    "id": "res_abc123",
                    "format": "musicxml",
                    "mime_type": "application/xml",
                    "available": True,
                    "license": "CC0-1.0",
                    "links": {
                        "download": f"{BASE}/scores/ave-verum.xml",
                        "view": f"{BASE}/scores/ave-verum",
                        "thumbnail": None,
                    },
                }
            ],
        }
    ]
}


class FakeHttp(ProviderHttpClient):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__(BASE, "application/vnd.osap-api.v1.3+json")
        self._payload = payload
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object] | None:
        self.calls.append((path, params))
        return self._payload


DEF_PATH = Path(__file__).resolve().parents[2] / "providers" / "omr"


def _provider() -> tuple[RemoteCatalogProvider, FakeHttp]:
    http = FakeHttp(SEARCH_PAYLOAD)
    provider = RemoteCatalogProvider(definition_path=DEF_PATH)
    provider._adapter._http = http  # type: ignore[attr-defined]
    return provider, http


class TestOMRSearch:
    def test_search_maps_works_to_candidates(self) -> None:
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

    def test_single_http_call_no_n_plus_one(self) -> None:
        provider, http = _provider()
        provider.search(SearchRequest(composer="Mozart"))
        assert len(http.calls) == 1

    def test_resolve_returns_first_candidate(self) -> None:
        provider, _ = _provider()
        result = provider.resolve(ResolveRequest(title="Ave Verum"))
        assert result is not None
        assert result.remote_id == "res_abc123"

    def test_empty_when_no_works(self) -> None:
        http = FakeHttp({})
        provider = RemoteCatalogProvider(definition_path=DEF_PATH)
        provider._adapter._http = http  # type: ignore[attr-defined]
        assert provider.search(SearchRequest(composer="Mozart")) == ()


class TestOMRInfo:
    def test_metadata_and_capabilities(self) -> None:
        provider, _ = _provider()
        assert provider.metadata().catalog_id.value == "omr"
        assert provider.metadata().name == "Open Music Repository"
        assert OutputFormat.MUSICXML in provider.capabilities().formats
