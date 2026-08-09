"""Level-2 protocol adapter for KernScores via GitHub mirrors.

kern.ccarh.org sufre timeouts (503); todo el catálogo Humdrum está replicado en los repos de
`humdrum-data` en GitHub. Este fetcher recorre esos repos (como ``GitHubFetcher`` para
OpenScore), filtra ficheros ``.krn`` y devuelve un Work con el **enlace directo** (raw) al
fichero. Se entrega lo que el proveedor da (formato ``kern``, sin conversión); la conversión a
MusicXML se hará en una fase posterior.
"""

import hashlib
import re

from src.osap.infrastructure.github import GitHubClient
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)

_KERN_EXTENSIONS = (".krn", ".kern")
DEFAULT_REPOS = ("humdrum-data/beethoven-piano-sonatas",)


class KernScoresFetcher(ProviderFetcher):
    """KernScores (humdrum-data GitHub mirrors) -> normalized contract JSON."""

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
                if not _is_kern(entry):
                    continue
                path = str(entry.get("path") or "")
                if not _matches(query, owner, name, path):
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
        root_sha = _root_tree_sha(self._github, owner, name)
        if root_sha is None:
            return branch, []
        tree = self._github.recursive_tree(owner, name, root_sha)
        self._index[repo] = (branch, tree)
        return branch, tree


def _root_tree_sha(github: GitHubClient, owner: str, name: str) -> str | None:
    entries = github.contents(owner, name, "")
    for entry in entries:
        if entry.get("type") == "tree" and entry.get("path") == name:
            sha = entry.get("sha")
            if isinstance(sha, str):
                return sha
    # Fallback: use the default branch tree via the repo root (not available here); return None.
    return None


def _is_kern(entry: dict[str, object]) -> bool:
    if entry.get("type") != "blob":
        return False
    return str(entry.get("path") or "").lower().endswith(_KERN_EXTENSIONS)


def _matches(query: ProviderQuery, owner: str, repo: str, path: str) -> bool:
    title_text = (query.title or query.query or "").strip()
    composer = (query.composer or "").strip()
    if not title_text and not composer:
        return False
    haystack = f"{repo} {path}".replace("_", " ").lower()
    if composer and composer.lower() not in haystack:
        return False
    return not (title_text and title_text.lower() not in path.replace("_", " ").lower())


def _to_work(owner: str, name: str, branch: str, path: str, entry: dict[str, object]) -> dict[str, object]:
    raw_url = f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{path}"
    resource_id = _stable_id(path)
    return {
        "id": resource_id,
        "title": _derive_title(path),
        "composer": _derive_composer(name),
        "catalogue": None,
        "license": "CC BY-SA 4.0",
        "public_domain": False,
        "resources": [
            {
                "id": resource_id,
                "format": "kern",
                "mime_type": "text/plain",
                "available": True,
                "license": "CC BY-SA 4.0",
                "download_url": raw_url,
                "view_url": raw_url,
                "thumbnail_url": None,
            }
        ],
    }


def _stable_id(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]  # noqa: S324


def _derive_composer(repo: str) -> str | None:
    segment = repo.replace("_", " ").strip()
    # humdrum-data repos suelen nombrarse "<composer>-<colección>".
    parts = re.split(r"[-–]", segment, maxsplit=1)
    return parts[0].strip().title() if parts else (segment.title() or None)


def _derive_title(path: str) -> str:
    filename = path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.(krn|kern)$", "", filename)
    stem = re.sub(r"^\d+\s*[._-]\s*", "", stem)
    return stem.replace("_", " ").strip() or "Untitled"
