from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.infrastructure.catalogs.openscore import OpenScoreCatalogProvider
from src.osap.infrastructure.github import GitHubClient

TREE: list[dict[str, object]] = [
    {
        "type": "blob",
        "path": "Schubert,_Franz/4_Lieder,_Op.96/1_Die_Sterne,_D.939/lc1.mxl",
        "size": 100,
        "sha": "aaa",
    },
    {
        "type": "blob",
        "path": "Schubert,_Franz/4_Lieder,_Op.96/2_Geheimes/lc2.mxl",
        "size": 90,
        "sha": "bbb",
    },
    {"type": "blob", "path": "Schubert,_Franz/other/thing.mscx", "size": 50, "sha": "ccc"},
    {"type": "blob", "path": "README.md", "size": 10, "sha": "ddd"},
]


class FakeGitHubClient(GitHubClient):
    def __init__(self) -> None:
        super().__init__()
        self.raw_calls: list[str] = []

    def default_branch(self, owner: str, repo: str) -> str:
        return "main"

    def contents(self, owner: str, repo: str, path: str) -> list[dict[str, object]]:
        return [{"name": "scores", "type": "dir", "sha": "scores-sha"}]

    def recursive_tree(self, owner: str, repo: str, tree_sha: str) -> list[dict[str, object]]:
        return TREE

    def raw(self, url: str) -> bytes:
        self.raw_calls.append(url)
        return b"<mxl/>"

    def raw_url(self, owner: str, repo: str, branch: str, path: str) -> str:
        return f"https://raw/{owner}/{repo}/{branch}/{path}"


def _provider() -> OpenScoreCatalogProvider:
    return OpenScoreCatalogProvider(FakeGitHubClient(), repos=("OpenScore/Lieder",))


class TestOpenScoreSearch:
    def test_search_by_title_and_composer(self) -> None:
        candidates = _provider().search(ResolveRequest(title="Die Sterne", composer="Schubert"))
        assert len(candidates) == 1
        assert candidates[0].work_descriptor.title == "Die Sterne, D.939"
        assert candidates[0].work_descriptor.composer == "Franz Schubert"
        assert candidates[0].format == OutputFormat.MUSICXML
        assert candidates[0].public_domain is True
        assert (
            candidates[0].download_url
            == "https://raw/OpenScore/Lieder/main/scores/Schubert,_Franz/4_Lieder,_Op.96/1_Die_Sterne,_D.939/lc1.mxl"
        )

    def test_partial_words(self) -> None:
        candidates = _provider().search(ResolveRequest(title="Sterne", composer="Schubert"))
        assert len(candidates) == 1

    def test_requires_match(self) -> None:
        assert _provider().search(ResolveRequest(title="Ave Maria", composer="Bruckner")) == ()

    def test_no_query_returns_empty(self) -> None:
        assert _provider().search(ResolveRequest()) == ()


class TestOpenScoreDownload:
    def test_download_returns_source(self) -> None:
        provider = _provider()
        candidates = provider.search(ResolveRequest(title="Die Sterne", composer="Schubert"))
        acquisition = provider.download(candidates[0])
        assert isinstance(acquisition, AcquisitionResult)
        assert acquisition.source.content == b"<mxl/>"
        assert acquisition.source.format == OutputFormat.MUSICXML


class TestOpenScoreInfo:
    def test_capabilities_and_metadata(self) -> None:
        provider = _provider()
        caps = provider.capabilities()
        assert caps.offline is False
        assert OutputFormat.MUSICXML in caps.formats
        assert provider.metadata().catalog_id.value == "openscore"
