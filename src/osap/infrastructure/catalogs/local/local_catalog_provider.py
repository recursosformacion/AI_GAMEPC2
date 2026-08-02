import json
from pathlib import Path

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
    WorkIdentifier,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.catalog_provider import ICatalogProvider

_PREFERRED_SCORE = (".mxl", ".xml", ".mei", ".mid", ".pdf")

_EXT_TO_FORMAT: dict[str, OutputFormat] = {
    ".mxl": OutputFormat.MUSICXML,
    ".xml": OutputFormat.MUSICXML,
    ".mei": OutputFormat.MEI,
    ".mid": OutputFormat.MIDI,
    ".midi": OutputFormat.MIDI,
    ".pdf": OutputFormat.PDF,
}


class LocalCatalogProvider(ICatalogProvider):
    """A catalog over the local OSAP library (already resolved works).

    Scans the library folder for stored works and returns them as candidates
    with a `local_path`, so the resolver can reuse them instead of downloading
    again. If nothing is stored, it returns NO RESULT (never an error).
    """

    def __init__(self, root: Path, name: str = "local") -> None:
        self._provider_id = ProviderId(name)
        self._root = root

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            offline=True,
            formats=(OutputFormat.MUSICXML, OutputFormat.PDF, OutputFormat.SCORE),
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId(self._provider_id.value),
            name=self._provider_id.value,
            provider_id=self.provider_id,
            source=str(self._root),
            status=CatalogStatus.AVAILABLE,
        )

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        if not self._root.exists():
            return ()
        candidates: list[CandidateRepresentation] = []
        for folder in self._root.iterdir():
            if not folder.is_dir():
                continue
            work = self._read_work(folder)
            if work is None:
                continue
            if not _matches(request, work):
                continue
            score_file = _score_file(folder)
            if score_file is None:
                continue
            fmt = _EXT_TO_FORMAT.get(score_file.suffix.lower(), OutputFormat.SCORE)
            candidates.append(
                CandidateRepresentation(
                    candidate_id=CandidateId(f"local-{folder.name}"),
                    work_descriptor=work,
                    provider_id=self.provider_id,
                    format=fmt,
                    origin="local_library",
                    license="local",
                    quality=QualityLevel.BASIC_MELODY,
                    confidence=Confidence(1.0),
                    local_path=str(score_file),
                    public_domain=True,
                    metadata={"folder": str(folder), "downloadable": True},
                )
            )
        return tuple(candidates)

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        candidates = self.search(request)
        return candidates[0] if candidates else None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        if not candidate.local_path:
            raise ScoreResolutionError("Local candidate has no local_path")
        path = Path(candidate.local_path)
        if not path.exists():
            raise ScoreResolutionError(f"Local file missing: {path}")
        data = path.read_bytes()
        fmt = candidate.format
        return AcquisitionResult(
            provider_id=self.provider_id,
            source=MusicalSource(
                SourceId(f"{candidate.candidate_id.value}:local"),
                data,
                fmt,
                {"source_url": candidate.local_path, "title": candidate.work_descriptor.title},
            ),
            confidence=Confidence(1.0),
            processing_time=Duration(0.0),
            format=fmt,
            quality_level=QualityLevel.BASIC_MELODY,
            diagnostics={"local_path": candidate.local_path},
        )

    def _read_work(self, folder: Path) -> WorkDescriptor | None:
        work_file = folder / "work.json"
        if not work_file.exists():
            return None
        try:
            data = json.loads(work_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        title = str(data.get("title") or "")
        if not title:
            return None
        wid = data.get("work_id")
        work_id = (
            WorkId(str(wid.get("value")))
            if isinstance(wid, dict) and wid.get("value")
            else WorkId(f"local-{folder.name}")
        )
        identifiers = tuple(
            WorkIdentifier(str(i.get("kind", "")), str(i.get("value", "")))
            for i in data.get("identifiers", [])
            if isinstance(i, dict)
        )
        return WorkDescriptor(
            work_id=work_id,
            title=title,
            subtitle=_opt(data, "subtitle"),
            composer=_opt(data, "composer"),
            arranger=_opt(data, "arranger"),
            lyricist=_opt(data, "lyricist"),
            language=_opt(data, "language"),
            movement=_opt(data, "movement"),
            genres=tuple(data.get("genres") or ()),
            instrumentation=tuple(data.get("instrumentation") or ()),
            voices=tuple(data.get("voices") or ()),
            identifiers=identifiers,
            metadata=dict(data.get("metadata") or {}),
        )


def _opt(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    return None if value is None else str(value)


def _score_file(folder: Path) -> Path | None:
    for ext in _PREFERRED_SCORE:
        candidate = folder / f"score{ext}"
        if candidate.exists():
            return candidate
    for child in folder.iterdir():
        if child.is_file() and child.name.startswith("score"):
            return child
    return None


def _matches(request: ResolveRequest, work: WorkDescriptor) -> bool:
    title_text = (request.title or request.query or "").strip()
    composer = (request.composer or "").strip()
    if not title_text and not composer:
        return True
    if composer and not MusicQueryNormalizer.matches(work.composer or "", composer):
        return False
    return not (title_text and not MusicQueryNormalizer.matches(work.title, title_text))
