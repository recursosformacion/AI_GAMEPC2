import csv
import enum
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any, cast

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.errors import ResourceUnavailableError
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
from src.osap.ports.catalog_provider import ICatalogProvider

ZENODO_CSV_URL = "https://zenodo.org/records/15571083/files/PDMX.csv?download=1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY,
    title TEXT, subtitle TEXT, composer_name TEXT, artist_name TEXT,
    license TEXT, license_conflict INTEGER, rating REAL, genres TEXT,
    seconds REAL, bars REAL, has_lyrics INTEGER, n_notes INTEGER, notes_per_bar REAL,
    no_license_conflict INTEGER, mxl TEXT, pdf TEXT, mid TEXT
);
CREATE VIRTUAL TABLE works_fts USING fts5(title, composer_name, content=);
"""
_INDEXES = ()
    id INTEGER PRIMARY KEY,
    title TEXT, subtitle TEXT, composer_name TEXT, artist_name TEXT,
    license TEXT, license_conflict INTEGER, rating REAL, genres TEXT,
    seconds REAL, bars REAL, has_lyrics INTEGER, n_notes INTEGER, notes_per_bar REAL,
    no_license_conflict INTEGER, mxl TEXT, pdf TEXT, mid TEXT
)
"""
_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_title ON works(title)",
    "CREATE INDEX IF NOT EXISTS idx_composer ON works(composer_name)",
)

_CSV_COLUMNS = [
    "title",
    "subtitle",
    "composer_name",
    "artist_name",
    "license",
    "license_conflict",
    "rating",
    "genres",
    "song_length.seconds",
    "song_length.bars",
    "has_lyrics",
    "n_notes",
    "notes_per_bar",
    "subset:no_license_conflict",
    "mxl",
    "pdf",
    "mid",
]


class PdmxUnavailableReason(enum.StrEnum):
    """Fine-grained reasons why PDMX may be unavailable.

    Each value implies a distinct user action (build index, wait for build,
    configure a mirror, retry the network, etc.). Never collapse all of them
    into a single "UNAVAILABLE".
    """

    INDEX_MISSING = "index_missing"
    INDEX_BUILDING = "index_building"
    INDEX_AVAILABLE = "index_available"
    MIRROR_NOT_CONFIGURED = "mirror_not_configured"
    DOWNLOAD_UNSUPPORTED = "download_unsupported"
    NETWORK_ERROR = "network_error"


class PdmxCatalogProvider(ICatalogProvider):
    """A catalog over the official PDMX metadata catalogue (PDMX.csv).

    Downloads/indexes only ``PDMX.csv`` (never the tarballs), searches over the
    local index, and returns individual works without reading the whole archive.
    """

    def __init__(
        self,
        csv_url: str = ZENODO_CSV_URL,
        index_path: Path | None = None,
        local_csv: Path | None = None,
        download_base: str | None = None,
    ) -> None:
        self._provider_id = ProviderId("pdmx")
        self._csv_url = csv_url
        self._index_path = index_path or Path("pdmx_index.db")
        self._local_csv = local_csv
        self._download_base = download_base
        self._building = False

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def availability(self) -> PdmxUnavailableReason:
        """The current PDMX availability state for the index."""
        if self._index_path.exists():
            return PdmxUnavailableReason.INDEX_AVAILABLE
        if self._building:
            return PdmxUnavailableReason.INDEX_BUILDING
        return PdmxUnavailableReason.INDEX_MISSING

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            offline=False,
            formats=(OutputFormat.MUSICXML, OutputFormat.PDF, OutputFormat.MIDI),
            metadata={
                "availability": self.availability().value,
                "index_available": self._index_path.exists(),
                "mirror_configured": self._download_base is not None,
            },
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("pdmx"),
            name="PDMX",
            provider_id=self.provider_id,
            source=ZENODO_CSV_URL,
            status=CatalogStatus.AVAILABLE if self._index_path.exists() else CatalogStatus.STALE,
        )

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        if not self._index_path.exists():
            raise ResourceUnavailableError(
                "PDMX index not built. Run 'osap datasets update pdmx' to build it from PDMX.csv.",
                code=self.availability().value,
            )
        rows = self._query(request)
        return tuple(
            _to_candidate(row, self._provider_id, downloadable=self._download_base is not None) for row in rows[:50]
        )

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        if not self._index_path.exists():
            return None
        rows = self._query(request)
        return _to_candidate(rows[0], self._provider_id, downloadable=self._download_base is not None) if rows else None

    def sync(self) -> None:
        """Build or refresh the local index from the official PDMX.csv."""
        self._building = True
        try:
            if self._local_csv and self._local_csv.exists():
                self._build_from_csv(self._local_csv)
                return
            if self._csv_url:
                self._download_csv_and_build()
                return
            raise ResourceUnavailableError(
                "PDMX index not built and no CSV source provided", code=self.availability().value
            )
        finally:
            self._building = False

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        path = str(candidate.metadata.get("path") or "")
        if not path:
            raise ResourceUnavailableError(
                "PDMX candidate has no file path", code=PdmxUnavailableReason.DOWNLOAD_UNSUPPORTED.value
            )
        if not self._download_base:
            raise ResourceUnavailableError(
                "Descarga individual no disponible en la distribución oficial. "
                "Configure download_base apuntando a un espejo que sirva la estructura /mxl/0/0/0/... "
                "para descargas por archivo.",
                code=PdmxUnavailableReason.MIRROR_NOT_CONFIGURED.value,
            )
        url = _mirror_url(self._download_base, path)
        data = _http_get(url)
        _validate_content(data, candidate.format, url)
        return AcquisitionResult(
            provider_id=self.provider_id,
            source=MusicalSource(SourceId(f"{candidate.candidate_id.value}:pdmx"), data, candidate.format),
            confidence=Confidence(1.0),
            processing_time=Duration(0.0),
            format=candidate.format,
            quality_level=QualityLevel.UNREADABLE,
            diagnostics={"source_url": url},
        )

    def _query(self, request: ResolveRequest) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[object] = []
        if request.title or request.query:
            token = (request.title or request.query or "").strip()
            if token:
                clauses.append("content MATCH ?")
                params.append(token)
        if request.composer:
            clauses.append("composer_name LIKE ?")
            params.append(f"%{request.composer}%")
        if request.desired_format is OutputFormat.MUSICXML:
            clauses.append("mxl IS NOT NULL AND mxl != ''")
        elif request.desired_format is OutputFormat.PDF:
            clauses.append("pdf IS NOT NULL AND pdf != ''")
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._conn() as conn:
            rows = conn.execute(f"SELECT * FROM works WHERE {where} ORDER BY rating DESC LIMIT 50", params).fetchall()
        return [dict(row) for row in rows]

    def _download_csv_and_build(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(urllib.request.urlopen(self._csv_url, timeout=120).read())  # noqa: S310
            tmp_path = Path(tmp.name)
        try:
            self._build_from_csv(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _build_from_csv(self, csv_path: Path) -> None:
        with self._conn() as conn:
                    conn.execute("DROP TABLE IF EXISTS works")
                    conn.execute(_SCHEMA)
            for index_sql in _INDEXES:
                conn.execute(index_sql)
            with csv_path.open("r", encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    conn.execute(
                        "INSERT OR IGNORE INTO works ("
                        "title,subtitle,composer_name,artist_name,license,license_conflict,rating,genres,"
                        "seconds,bars,has_lyrics,n_notes,notes_per_bar,no_license_conflict,mxl,pdf,mid) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            _s(row, "title"),
                            _s(row, "subtitle"),
                            _s(row, "composer_name"),
                            _s(row, "artist_name"),
                            _s(row, "license"),
                            _b(row, "license_conflict"),
                            _f(row, "rating"),
                            _s(row, "genres"),
                            _f(row, "song_length.seconds"),
                            _f(row, "song_length.bars"),
                            _b(row, "has_lyrics"),
                            _i(row, "n_notes"),
                            _f(row, "notes_per_bar"),
                            _b(row, "subset:no_license_conflict"),
                            _s(row, "mxl"),
                            _s(row, "pdf"),
                            _s(row, "mid"),
                        ),
                    )

    def _conn(self) -> sqlite3.Connection:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._index_path)
        conn.row_factory = sqlite3.Row
        return conn


def _s(row: dict[str, str], key: str) -> str:
    return row.get(key, "") or ""


def _f(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _i(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "") or 0))
    except (TypeError, ValueError):
        return 0


def _b(row: dict[str, str], key: str) -> int:
    return 1 if str(row.get(key, "")).lower() in ("true", "1", "yes") else 0


def _to_candidate(row: dict[str, Any], provider_id: ProviderId, downloadable: bool = True) -> CandidateRepresentation:
    title = str(row.get("title") or "Untitled")
    file_path = str(row.get("mxl") or row.get("pdf") or row.get("mid") or "")
    fmt = _format_for(row)
    public_domain = not bool(row.get("license_conflict"))
    return CandidateRepresentation(
        candidate_id=CandidateId(f"pdmx-{row.get('id')}"),
        work_descriptor=WorkDescriptor(
            work_id=WorkId(f"pdmx-{row.get('id')}"),
            title=title,
            subtitle=_opt(row, "subtitle"),
            composer=_opt(row, "composer_name"),
            language=None,
        ),
        provider_id=provider_id,
        format=fmt,
        origin="pdmx",
        license=_opt(row, "license"),
        quality=QualityLevel.BASIC_MELODY,
        confidence=Confidence(min(float(row.get("rating") or 0) / 5.0, 1.0)),
        public_domain=public_domain,
        local_path=None,
        metadata={
            "path": file_path,
            "composer": row.get("composer_name"),
            "genres": row.get("genres"),
            "duration_seconds": row.get("seconds"),
            "downloadable": downloadable,
        },
    )


def _opt(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    return None if value in (None, "") else str(value)


def _format_for(row: dict[str, Any]) -> OutputFormat:
    if row.get("mxl"):
        return OutputFormat.MUSICXML
    if row.get("pdf"):
        return OutputFormat.PDF
    if row.get("mid"):
        return OutputFormat.MIDI
    return OutputFormat.SCORE


def _mirror_url(download_base: str, path: str) -> str:
    base = download_base.rstrip("/")
    if path.startswith("./"):
        path = path[2:]
    return f"{base}/{path}"


def _http_get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
            return cast("bytes", response.read())
    except Exception as exc:  # noqa: BLE001
        raise ResourceUnavailableError(
            f"PDMX mirror request failed: {url}", code=PdmxUnavailableReason.NETWORK_ERROR.value
        ) from exc


def _validate_content(data: bytes, format: OutputFormat, url: str) -> None:
    if format is OutputFormat.MUSICXML and not (data.startswith(b"PK") or b"<score" in data[:500]):
        raise ResourceUnavailableError(f"PDMX mirror returned invalid MusicXML: {url}")
    if format is OutputFormat.PDF and not data.startswith(b"%PDF"):
        raise ResourceUnavailableError(f"PDMX mirror returned invalid PDF: {url}")
    if not data:
        raise ResourceUnavailableError(f"PDMX mirror returned empty content: {url}")
