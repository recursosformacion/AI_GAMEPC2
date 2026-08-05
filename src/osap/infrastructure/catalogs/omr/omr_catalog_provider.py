from typing import Any

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.cost_level import CostLevel
from src.osap.domain.errors import ResourceUnavailableError, ScoreResolutionError
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
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
from src.osap.infrastructure.http.http_client import HttpClient, HttpError
from src.osap.ports.catalog_provider import ICatalogProvider

_PROVIDER_ID = ProviderId("omr")
_DEFAULT_VERSION = "1.2"


class OmrCatalogProvider(ICatalogProvider):
    """Open Music Repository as a standard `ICatalogProvider`.

    Talks to the OMR HTTP API (see `docs/provider-api-contract.md`). It is a
    provider like any other: no special path, no privileges, no
    `if provider == "omr"` anywhere in the core.
    """

    def __init__(
        self,
        http: HttpClient,
        base_url: str,
        api_key: str | None = None,
        version: str = _DEFAULT_VERSION,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._version = version
        self._provider_id = _PROVIDER_ID

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            supports_search=True,
            supports_download=True,
            offline=False,
            formats=(OutputFormat.MUSICXML, OutputFormat.PDF, OutputFormat.MIDI, OutputFormat.JSON),
            cost_level=CostLevel.EXPENSIVE,
            supports_composer=True,
            supports_catalogue=True,
            metadata={"source": "http", "base_url": self._base_url, "version": self._version},
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("omr"),
            name="Open Music Repository",
            provider_id=self.provider_id,
            source=self._base_url,
            status=CatalogStatus.INSTALLED,
            version=self._version,
        )

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        params: dict[str, str] = {"type": "score", "page": "1", "per_page": "50"}
        query = (request.query or request.title or "").strip()
        if query:
            params["q"] = query
        if request.composer:
            params["composer"] = request.composer
        if request.catalogue:
            params["catalog"] = request.catalogue
        url = self._http.build_url(self._base_url, "/api/search", params)
        try:
            payload = self._http.get_json(url, headers=self._headers())
        except HttpError as exc:
            raise ResourceUnavailableError(f"OMR search unavailable: {exc}", code="http") from exc
        resources = _resources(payload)
        return tuple(self._to_candidate(resource) for resource in resources)

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        candidates = self.search(SearchRequest.from_resolve(request))
        return candidates[0] if candidates else None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        url = candidate.download_url
        if not url:
            raise ScoreResolutionError(f"OMR candidate {candidate.candidate_id.value} has no download URL")
        try:
            data = self._http.get(url, headers=self._headers())
        except HttpError as exc:
            raise ResourceUnavailableError(f"OMR download unavailable: {exc}", code="http") from exc
        fmt = output_format or candidate.format
        source = MusicalSource(
            SourceId(f"omr-{candidate.remote_id or candidate.candidate_id.value}"),
            data,
            fmt,
            {"source_url": url, "title": candidate.work_descriptor.title},
        )
        return AcquisitionResult(
            provider_id=self.provider_id,
            source=source,
            confidence=Confidence(0.9),
            processing_time=Duration(0.0),
            format=fmt,
            quality_level=QualityLevel.BASIC_MELODY,
            diagnostics={"source_url": url},
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": f"application/vnd.osap-api.v{self._version}+json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    def _to_candidate(self, resource: dict[str, Any]) -> CandidateRepresentation:
        rid = str(resource.get("id") or "")
        title = str(resource.get("title") or "Untitled")
        raw_access = resource.get("access")
        access: dict[str, Any] = raw_access if isinstance(raw_access, dict) else {}
        raw_formats = resource.get("formats")
        formats: list[Any] = raw_formats if isinstance(raw_formats, list) else []
        mode = str(access.get("mode") or "direct")
        license_text = str(access.get("license") or "")
        fmt = _to_output_format(formats)
        return CandidateRepresentation(
            candidate_id=CandidateId(f"omr-{rid}"),
            work_descriptor=WorkDescriptor(
                work_id=WorkId(f"omr-{rid}"),
                title=title,
                composer=_str_or_none(resource.get("composer")),
                catalogue_number=_str_or_none(resource.get("catalog")),
            ),
            provider_id=self.provider_id,
            format=fmt,
            origin="omr",
            license=license_text or None,
            quality=QualityLevel.BASIC_MELODY,
            confidence=Confidence(0.9),
            download_url=_str_or_none(access.get("url")),
            public_domain=_is_public_domain(license_text),
            downloadable=mode == "direct",
            manual_download=mode == "manual",
            remote_id=rid,
            metadata={
                "raw_type": str(resource.get("type") or "score"),
                "expires": access.get("expires"),
            },
        )


def _resources(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    resources = payload.get("resources")
    if not isinstance(resources, list):
        return []
    return [r for r in resources if isinstance(r, dict)]


def _to_output_format(formats: list[object]) -> OutputFormat:
    mapping = {
        "xml": OutputFormat.MUSICXML,
        "mxl": OutputFormat.MUSICXML,
        "musicxml": OutputFormat.MUSICXML,
        "pdf": OutputFormat.PDF,
        "mid": OutputFormat.MIDI,
        "midi": OutputFormat.MIDI,
        "mei": OutputFormat.MEI,
        "json": OutputFormat.JSON,
        "score": OutputFormat.SCORE,
    }
    for value in formats:
        candidate = mapping.get(str(value).lower())
        if candidate is not None:
            return candidate
    return OutputFormat.PDF


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_public_domain(license_text: str) -> bool:
    lowered = license_text.lower()
    return "public domain" in lowered or "cc0" in lowered
