import json

from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.github import GitHubClient


class StubGitHubClient(GitHubClient):
    def __init__(self, payloads: dict[str, bytes], cache: InMemoryCache | None = None) -> None:
        super().__init__(cache=cache)
        self._payloads = payloads
        self.get_calls = 0

    def _get(self, url: str) -> bytes:
        self.get_calls += 1
        if url in self._payloads:
            return self._payloads[url]
        raise AssertionError(f"unexpected url {url}")


class TestGitHubClient:
    def test_raw_url(self) -> None:
        client = GitHubClient()
        url = client.raw_url("OpenScore", "Lieder", "main", "scores/Schubert,_Franz/x.mxl")
        assert url == "https://raw.githubusercontent.com/OpenScore/Lieder/main/scores/Schubert%2C_Franz/x.mxl"

    def test_default_branch_parses(self) -> None:
        repo = json.dumps({"default_branch": "main"}).encode()
        client = StubGitHubClient({"https://api.github.com/repos/OpenScore/Lieder": repo})
        assert client.default_branch("OpenScore", "Lieder") == "main"

    def test_recursive_tree_parses(self) -> None:
        tree = json.dumps({"tree": [{"path": "a.mxl", "type": "blob"}]}).encode()
        client = StubGitHubClient({"https://api.github.com/repos/O/R/git/trees/scores-sha?recursive=1": tree})
        result = client.recursive_tree("O", "R", "scores-sha")
        assert result == [{"path": "a.mxl", "type": "blob"}]

    def test_get_json_uses_cache(self) -> None:
        payload = json.dumps({"ok": True}).encode()
        url = "https://api.github.com/repos/O/R"
        cache = InMemoryCache()
        client = StubGitHubClient({url: payload}, cache=cache)
        assert client.default_branch("O", "R") == "main"  # triggers _get_json
        first_calls = client.get_calls
        assert client.default_branch("O", "R") == "main"
        assert client.get_calls == first_calls  # cached, no extra HTTP

    def test_headers_include_token(self) -> None:
        client = GitHubClient(token="secret")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer secret"
        assert "Accept" in headers
