import re

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.errors import ScoreResolutionError
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
from src.osap.infrastructure.mediawiki import MediaWikiClient
from src.osap.ports.catalog_provider import ICatalogProvider

_COPOSER_CATEGORY_RE = re.compile(r"Works by (.+)")
_MIME_TO_FORMAT: dict[str, OutputFormat] = {
    "application/pdf": OutputFormat.PDF,
    "image/vnd.musicxml": OutputFormat.MUSICXML,
    "application/vnd.recordare.musicxml": OutputFormat.MUSICXML,
    "application/vnd.recordare.musicxml+xml": OutputFormat.MUSICXML,
    "audio/midi": OutputFormat.MIDI,
}


class IMSLPCatalogProvider(ICatalogProvider):
    """Catalog over IMSLP using the official MediaWiki API.

    Uses only the documented MediaWiki API (imslp.org/api.php): search, category
    traversal, page revisions and image info. No HTML scraping. No deprecated
    endpoints. The ``api.imslp.org/petrucci_api.php`` endpoint is NOT used.
    """

    def __init__(self, mw: MediaWikiClient) -> None:
        self._mw = mw
        self._provider_id = ProviderId("imslp")

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            supports_search=True,
            supports_download=True,
            offline=False,
            formats=(OutputFormat.PDF, OutputFormat.MUSICXML, OutputFormat.MIDI),
            metadata={"source": "imslp", "api": "mediawiki"},
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("imslp"),
            name="IMSLP",
            provider_id=self.provider_id,
            source="imslp.org",
            status=CatalogStatus.AVAILABLE,
        )

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        query = _build_search(request)
        if not query:
            return ()
        raw = self._mw.search(query, namespace=0, limit=25)
        candidates: list[CandidateRepresentation] = []
        for result in raw:
            title = str(result.get("title") or "")
            snippet = str(result.get("snippet") or "")
            if not title or _is_non_work(title, snippet):
                continue
            candidates.append(self._to_candidate(title, result))
        return tuple(candidates)

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        candidates = self.search(request)
        return candidates[0] if candidates else None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        page_title = str(candidate.metadata.get("page_title") or candidate.work_descriptor.title)
        file_titles = self._mw.page_images(page_title)
        if not file_titles:
            raise ScoreResolutionError(f"No files found on page {page_title}")
        target = output_format or candidate.format
        best = _pick_best(self._mw, file_titles, target)
        if best is None:
            raise ScoreResolutionError(f"No downloadable {target.value} file found for {page_title}")
        data = self._mw.download(str(best["url"]))
        fmt = _mime_to_format(str(best.get("mime", "")))
        if fmt is OutputFormat.PDF and not data.startswith(b"%PDF"):
            raise ScoreResolutionError(
                "El PDF de IMSLP requiere descarga manual (verificación anti-bot). "
                f"Abre la página del archivo en tu navegador: {best.get('descriptionurl') or best['url']}"
            )
        source = MusicalSource(
            SourceId(f"{candidate.candidate_id.value}:{fmt.value}"),
            data,
            fmt,
            {"source_url": best["url"], "title": candidate.work_descriptor.title},
        )
        return AcquisitionResult(
            provider_id=self.provider_id,
            source=source,
            confidence=Confidence(0.9),
            processing_time=Duration(0.0),
            format=fmt,
            quality_level=QualityLevel.UNREADABLE,
            diagnostics={"source_url": best["url"]},
        )

    def _to_candidate(self, title: str, result: dict[str, object]) -> CandidateRepresentation:
        snippet = str(result.get("snippet") or "")
        composer = _extract_composer(title)
        public_domain = None if not snippet else "public domain" in snippet.lower()
        return CandidateRepresentation(
            candidate_id=CandidateId(f"imslp-{_hash(title)}"),
            work_descriptor=WorkDescriptor(
                work_id=WorkId(f"imslp-{_hash(title)}"),
                title=title,
                composer=composer,
            ),
            provider_id=self.provider_id,
            format=OutputFormat.PDF,
            confidence=Confidence(0.7),
            public_domain=public_domain,
            license="public domain" if public_domain is True else None,
            origin="imslp.org",
            metadata={"page_title": title, "snippet": snippet, "downloadable": False},
        )


_NON_WORK_PREFIXES = (
    "List of",
    "Wishlist",
    "Category:",
    "Special:",
    "IMSLP:",
    "Template:",
    "File:",
    "Help:",
    "User:",
    "Talk:",
    "Edition ",
)

_WORK_TITLE_RE = re.compile(r"\(.+\)")


def _is_non_work(title: str, snippet: str) -> bool:
    if title.startswith(_NON_WORK_PREFIXES) or snippet.startswith("#REDIRECT"):
        return True
    return not bool(_WORK_TITLE_RE.search(title))


def _build_search(request: ResolveRequest) -> str:
    parts: list[str] = []
    if request.title or request.query:
        parts.append(request.title or request.query or "")
    if request.composer:
        parts.append(request.composer)
    return " ".join(parts).strip()


def _extract_composer(title: str) -> str | None:
    match = re.search(r"\((.+)\)", title)
    if not match:
        return None
    inner = match.group(1)
    parts = inner.rsplit(",", 1)
    if len(parts) == 2:
        return f"{parts[1].strip()} {parts[0].strip()}"
    return inner.strip() or None


_SCORE_EXTENSIONS = (".pdf", ".mxl", ".musicxml", ".xml", ".mid", ".midi", ".zip")


def _pick_best(mw: "MediaWikiClient", file_titles: list[str], preferred: OutputFormat) -> dict[str, object] | None:
    """Batch-query imageinfo for score-like files in a single API call."""
    score_files = [ft for ft in file_titles[:50] if ft.lower().replace("file:", "").endswith(_SCORE_EXTENSIONS)]
    if not score_files:
        return None
    infos = mw.images_info_batch(score_files)
    if not infos:
        return None
    preferred_mimes = {mime for mime, fmt in _MIME_TO_FORMAT.items() if fmt == preferred}
    for info in infos:
        if str(info.get("mime", "")) in preferred_mimes:
            return info
    return infos[0]


def _mime_to_format(mime: str) -> OutputFormat:
    return _MIME_TO_FORMAT.get(mime.lower(), OutputFormat.PDF)


def _hash(text: str) -> str:
    import hashlib

    return hashlib.sha1(text.encode()).hexdigest()[:16]  # noqa: S324
