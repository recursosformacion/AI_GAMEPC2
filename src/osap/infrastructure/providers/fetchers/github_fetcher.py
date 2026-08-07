"""Level-2 protocol adapter for OpenScore.

Talks to the GitHub API and returns JSON equivalent to the provider contract
(`works` -> list of Work dicts, each with `resources`). The result flows through the
same mapping pipeline as any Level-1 REST provider.
"""

import re

from src.osap.domain.music_query_normalizer import MusicQueryNormalizer
from src.osap.infrastructure.github import GitHubClient
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)

_MUSICXML_EXTENSIONS = (".mxl", ".musicxml", ".xml")
DEFAULT_REPOS = ("OpenScore/Lieder",)


class GitHubFetcher(ProviderFetcher):
    """OpenScore (GitHub) -> normalized contract JSON."""

    def __init__(self, github: GitHubClient, repos: tuple[str, ...] = DEFAULT_REPOS) -> None:
        self._github = github
        self._repos = repos
        self._index: dict[str, tuple[str, list[dict[str, object]]]] = {}

    def fetch(
        self, definition: ProviderDefinition, endpoint: Endpoint, query: ProviderQuery
    ) -> dict[str, object] | None:
        works: list[dict[str, object]] = []
        for repo in self._repos:
            owner, name = repo.split("/", 1)
            branch, tree = self._index_for(repo)
            for entry in tree:
                if not _is_musicxml(entry):
                    continue
                path = str(entry.get("path") or "")
                if not _matches(query, path):
                    continue
                works.append(_to_work(owner, name, branch, path, entry))
        return {"works": works}

    def fetch_resource(
        self, definition: ProviderDefinition, endpoint: Endpoint, work_id: str
    ) -> dict[str, object] | None:
        return None

    def _index_for(self, repo: str) -> tuple[str, list[dict[str, object]]]:
        if repo in self._index:
            return self._index[repo]
        owner, name = repo.split("/", 1)
        branch = self._github.default_branch(owner, name)
        root = self._github.contents(owner, name, "")
        scores_sha: str | None = None
        for entry in root:
            if entry.get("name") == "scores" and entry.get("type") == "dir":
                scores_sha = str(entry.get("sha"))
                break
        if scores_sha is None:
            return branch, []
        tree = self._github.recursive_tree(owner, name, scores_sha)
        self._index[repo] = (branch, tree)
        return branch, tree


def _is_musicxml(entry: dict[str, object]) -> bool:
    if entry.get("type") != "blob":
        return False
    return str(entry.get("path") or "").lower().endswith(_MUSICXML_EXTENSIONS)


def _matches(query: ProviderQuery, path: str) -> bool:
    title_text = (query.title or query.query or "").strip()
    composer = (query.composer or "").strip()
    if not title_text and not composer:
        return False
    haystack = path.replace("_", " ")
    if composer and not MusicQueryNormalizer.matches(path.split("/")[0].replace("_", " "), composer):
        return False
    return not (title_text and not MusicQueryNormalizer.matches(haystack, title_text))


def _to_work(owner: str, name: str, branch: str, path: str, entry: dict[str, object]) -> dict[str, object]:
    full_path = f"scores/{path}"
    raw_url = f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{full_path}"
    composer = _derive_composer(path)
    title = _derive_title(path)
    resource_id = _stable_id(path)
    return {
        "id": resource_id,
        "title": title,
        "composer": composer,
        "catalogue": None,
        "license": "CC0-1.0",
        "public_domain": True,
        "resources": [
            {
                "id": resource_id,
                "format": "musicxml",
                "mime_type": "application/vnd.recordare.musicxml+xml",
                "available": True,
                "license": "CC0-1.0",
                "download_url": raw_url,
                "view_url": raw_url,
                "thumbnail_url": None,
            }
        ],
    }


def _stable_id(path: str) -> str:
    import hashlib

    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]  # noqa: S324


def _derive_composer(path: str) -> str | None:
    parts = path.split("/")
    if not parts:
        return None
    segment = parts[0].replace("_", " ").strip()
    if "," in segment:
        last, first = segment.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return segment or None


def _derive_title(path: str) -> str:
    parts = path.split("/")
    segment = parts[-2] if len(parts) >= 2 else (parts[0] if parts else path)
    segment = re.sub(r"^\d+\s*[._-]\s*", "", segment)
    return segment.replace("_", " ").strip() or "Untitled"
