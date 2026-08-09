"""V1 — Tests del fetcher de KernScores (humdrum-data GitHub mirrors)."""

from __future__ import annotations

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery
from src.osap.infrastructure.providers.fetchers.kernscores_fetcher import KernScoresFetcher


class _FakeGitHub:
    def default_branch(self, owner: str, repo: str) -> str:
        return "master"

    def contents(self, owner: str, repo: str, path: str) -> list[dict[str, object]]:
        return [{"type": "tree", "path": repo, "sha": "root-sha"}]

    def recursive_tree(self, owner: str, repo: str, tree_sha: str) -> list[dict[str, object]]:
        return [
            {"type": "blob", "path": "sonatas/sonata01-1.krn"},
            {"type": "blob", "path": "sonatas/sonata01-2.krn"},
            {"type": "blob", "path": "README.md"},
        ]


def _query(composer: str | None = None, title: str | None = None, text: str = "") -> ProviderQuery:
    return ProviderQuery(query=text, composer=composer, title=title, limit=50)


def test_kernscores_fetcher_returns_kern_links() -> None:
    github = _FakeGitHub()
    fetcher = KernScoresFetcher(github=github, repos=("humdrum-data/beethoven-piano-sonatas",))
    result = fetcher.fetch(None, None, _query(composer="beethoven", title="sonata01-1"))
    works = result["works"]
    assert isinstance(works, list) and len(works) == 1
    work = works[0]
    assert "sonata01-1" in work["title"]
    resources = work["resources"]
    assert isinstance(resources, list) and len(resources) == 1
    res = resources[0]
    # Se entrega el enlace directo (raw) y el formato que da el proveedor (kern), sin conversión.
    assert res["format"] == "kern"
    assert res["download_url"] == "https://raw.githubusercontent.com/humdrum-data/beethoven-piano-sonatas/master/sonatas/sonata01-1.krn"
    assert res["available"] is True


def test_kernscores_fetcher_filters_by_query() -> None:
    github = _FakeGitHub()
    fetcher = KernScoresFetcher(github=github, repos=("humdrum-data/beethoven-piano-sonatas",))
    result = fetcher.fetch(None, None, _query(composer="mozart"))
    assert result["works"] == []
