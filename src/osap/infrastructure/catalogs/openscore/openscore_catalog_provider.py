import re

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.music_query_normalizer import MusicQueryNormalizer
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    Duration,
    ProviderId,
    SourceId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.github import GitHubClient
from src.osap.ports.catalog_provider import ICatalogProvider

_MUSICXML_EXTENSIONS = (".mxl", ".musicxml", ".xml")
DEFAULT_REPOS = ("OpenScore/Lieder",)


class OpenScoreCatalogProvider(ICatalogProvider):
    """A catalog over the official OpenScore repositories on GitHub.

    Uses only the GitHub REST API (repo tree) and raw.githubusercontent URLs;
    no scraping. Locates MusicXML files (.mxl/.musicxml/.xml) by title and
    composer using partial-word matching on the repository paths.
    """

    def __init__(self, github: GitHubClient, repos: tuple[str, ...] = DEFAULT_REPOS) -> None:
        self._github = github
        self._repos = repos
        self._provider_id = ProviderId("openscore")
        self._index: dict[str, tuple[str, list[dict[str, object]]]] = {}

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            supports_search=True,
            supports_download=True,
            offline=False,
            formats=(OutputFormat.MUSICXML,),
            public_domain_only=True,
            metadata={"source": "github", "repos": self._repos},
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("openscore"),
            name="OpenScore",
            provider_id=self.provider_id,
            source=", ".join(self._repos),
            status=CatalogStatus.INSTALLED,
        )

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        candidates: list[CandidateRepresentation] = []
        for repo in self._repos:
            branch, tree = self._load_index(repo)
            for entry in tree:
                if not self._is_musicxml(entry):
                    continue
                path = str(entry.get("path") or "")
                if not self._matches(request, path):
                    continue
                candidates.append(self._to_candidate(repo, branch, path, entry))
        return tuple(candidates)

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        candidates = self.search(request)
        return candidates[0] if candidates else None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        repo = str(candidate.metadata.get("repo") or "")
        branch = str(candidate.metadata.get("branch") or "main")
        path = str(candidate.metadata.get("path") or "")
        if candidate.download_url:
            data = self._github.raw(candidate.download_url)
        else:
            owner, name = repo.split("/", 1)
            url = self._github.raw_url(owner, name, branch, path)
            data = self._github.raw(url)
        source = MusicalSource(
            SourceId(f"{candidate.candidate_id.value}:musicxml"),
            data,
            OutputFormat.MUSICXML,
            {"source_url": candidate.download_url, "title": candidate.work_descriptor.title},
        )
        return AcquisitionResult(
            provider_id=self.provider_id,
            source=source,
            confidence=Confidence(0.95),
            processing_time=Duration(0.0),
            format=OutputFormat.MUSICXML,
            quality_level=QualityLevel.BASIC_MELODY,
            diagnostics={"source_url": candidate.download_url},
        )

    def _load_index(self, repo: str) -> tuple[str, list[dict[str, object]]]:
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
            raise ScoreResolutionError(f"No 'scores' directory in {repo}")
        tree = self._github.recursive_tree(owner, name, scores_sha)
        self._index[repo] = (branch, tree)
        return branch, tree

    @staticmethod
    def _is_musicxml(entry: dict[str, object]) -> bool:
        if entry.get("type") != "blob":
            return False
        return str(entry.get("path") or "").lower().endswith(_MUSICXML_EXTENSIONS)

    @staticmethod
    def _matches(request: ResolveRequest, path: str) -> bool:
        title_text = (request.title or request.query or "").strip()
        composer = (request.composer or "").strip()
        if not title_text and not composer:
            return False
        haystack = path.replace("_", " ")
        if composer and not MusicQueryNormalizer.matches(path.split("/")[0].replace("_", " "), composer):
            return False
        return not (title_text and not MusicQueryNormalizer.matches(haystack, title_text))

    def _to_candidate(self, repo: str, branch: str, path: str, entry: dict[str, object]) -> CandidateRepresentation:
        owner, name = repo.split("/", 1)
        full_path = f"scores/{path}"
        raw_url = self._github.raw_url(owner, name, branch, full_path)
        composer = _derive_composer(path)
        title = _derive_title(path)
        return CandidateRepresentation(
            candidate_id=CandidateId(f"openscore-{_stable_id(path)}"),
            work_descriptor=WorkDescriptor(
                work_id=WorkId(f"openscore-{_stable_id(path)}"), title=title, composer=composer
            ),
            provider_id=self.provider_id,
            format=OutputFormat.MUSICXML,
            origin=repo,
            license="CC0-1.0",
            quality=QualityLevel.BASIC_MELODY,
            confidence=Confidence(0.8),
            download_url=raw_url,
            public_domain=True,
            size_bytes=_as_int(entry.get("size")),
            checksum=str(entry.get("sha") or None),
            metadata={"repo": repo, "branch": branch, "path": full_path, "downloadable": True},
        )


def _stable_id(path: str) -> str:
    import hashlib

    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]  # noqa: S324


def _as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return None


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
