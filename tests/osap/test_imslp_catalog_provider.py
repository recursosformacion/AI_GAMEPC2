from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.resolve_request import ResolveRequest
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
        candidates = _provider().search(ResolveRequest(title="Cançó de Comiat", composer="Toldrà"))
        assert len(candidates) == 1
        assert candidates[0].work_descriptor.title == "Cançó de Comiat (Toldrà, Eduard)"
        assert candidates[0].work_descriptor.composer == "Eduard Toldrà"
        assert candidates[0].public_domain is True

    def test_empty_when_no_match(self) -> None:
        assert _provider().search(ResolveRequest(title="Nosuchwork")) == ()

    def test_resolve_returns_first(self) -> None:
        candidate = _provider().resolve(ResolveRequest(title="Cançó de Comiat"))
        assert candidate is not None
        assert candidate.public_domain is True

    def test_download_returns_source(self) -> None:
        mw = FakeMediaWikiClient()
        provider = IMSLPCatalogProvider(mw)
        candidates = provider.search(ResolveRequest(title="Cançó de Comiat"))
        acquisition = provider.download(candidates[0])
        assert isinstance(acquisition, AcquisitionResult)
        assert acquisition.source.content == b"%PDF-1.4"
        assert len(mw.downloads) == 1
