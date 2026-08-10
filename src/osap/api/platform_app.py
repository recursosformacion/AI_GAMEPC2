"""V3.1 — OSAP Platform API (FastAPI HTTP adapter).

Thin HTTP layer over `PlatformApi` (Application API). It only serializes/validates the
public contract DTOs and returns the uniform envelope. It never talks to the domain
directly. Auth is prepared (Bearer) but disabled in V3.1.
"""

from __future__ import annotations

import logging
import re
import urllib.request
import uuid
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI, Header, Query, Response
from fastapi.responses import StreamingResponse

from src.osap.api.contracts import (
    ComposerCreationEvidenceResponse,
    ComposerDetailResponse,
    ComposerListResponse,
    ComposerStatisticsResponse,
    ComposerSummaryResponse,
    ComposerWorkRefResponse,
    ComposerWorksResponse,
    CreateComposerRequest,
    DiscoverSource,
    ErrorBody,
    ErrorEnvelope,
    IntentResponse,
    JobCreateRequest,
    JobResponse,
    KnowledgeFactDTO,
    KnowledgeObservationDTO,
    KnowledgeSuggestionDTO,
    MergeComposersRequest,
    MergeComposersResultResponse,
    ProviderResponse,
    RegisterRequest,
    RepositorySource,
    RepositorySourceSummary,
    ReviewComposerRequest,
    SearchModel,
    SearchRequest,
    SearchResponse,
    SessionSource,
    SessionSourceCreate,
    SuccessEnvelope,
    SystemHealthResponse,
    SystemStatisticsResponse,
    SystemVersionResponse,
    VerifyEmailRequest,
    VoteRequest,
    VoteResponse,
    VotesOverviewResponse,
    WorkStatisticsResponse,
)
from src.osap.api.platform import VERSION, PlatformApi
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire
from src.osap.domain.votes import (
    DuplicateVoteError,
    ForbiddenError,
    InvalidVoteError,
    UnauthenticatedError,
    WorkNotFoundError,
)
from src.osap.infrastructure.auth.auth_proxy_client import AuthProxyError
from src.osap.infrastructure.persistence.storage_vote_store import StorageUnavailableError
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from src.osap.api.platform import KnowledgeStore


_EXTENSION = {"musicxml": ".musicxml", "pdf": ".pdf", "midi": ".mid"}


def _download_filename(info: dict[str, object]) -> str:
    composer = str(info.get("composer") or "")
    title = str(info.get("title") or "representation")
    catalogue = str(info.get("catalogue") or "")
    base = f"{composer} - {title}".strip(" -")
    if catalogue:
        base = f"{base} {catalogue}".strip()
    ext = _EXTENSION.get(str(info.get("format") or ""), ".bin")
    return re.sub(r'[\\/:*?"<>|]+', "_", base) + ext


_MEDIA_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "musicxml": "application/vnd.recordare.musicxml+xml",
    "midi": "audio/midi",
}


def _media_type_for_format(fmt: str) -> str:
    return _MEDIA_TYPES.get(fmt, "application/octet-stream")


def _configure_osap_logging() -> None:
    logger = logging.getLogger("osap.api")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False


_TAGS = [
    {"name": "Searches", "description": "Create and retrieve searches."},
    {"name": "Jobs", "description": "Orchestrate long-running tasks."},
    {"name": "Providers", "description": "Provider state and capabilities."},
    {"name": "Knowledge", "description": "Learned knowledge (read-only)."},
    {"name": "Votes", "description": "Votación de obras y estadísticas agregadas."},
    {"name": "System", "description": "Health, version and statistics."},
]


def _request_id() -> str:
    return uuid.uuid4().hex


def _example(data: object) -> dict[str, Any]:
    return {"success": True, "request_id": "example-request-id", "data": data}


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "request_id": "example-request-id",
        "error": {"code": code, "message": message, "details": {}},
    }


def _resp(description: str, example: dict[str, Any]) -> dict[str, Any]:
    return {"description": description, "content": {"application/json": {"example": example}}}


_INVALID_QUERY_400 = _resp("Invalid query", _error("INVALID_QUERY", "Query cannot be empty"))
_INVALID_JOB_400 = _resp("Invalid job type", _error("INVALID_JOB_TYPE", "Job type cannot be empty"))
_NOT_FOUND_404 = _resp("Resource not found", _error("NOT_FOUND", "Resource not found"))
_VALIDATION_422 = _resp("Validation error", _error("VALIDATION", "Request validation failed"))
_INTERNAL_500 = _resp("Internal server error", _error("INTERNAL", "Unexpected server error"))

_SEARCH_CREATED_201 = _resp(
    "Search created",
    _example(
        {
            "search_id": "9f2c0a1b",
            "results": [
                {
                    "work": {
                        "work_id": "w1",
                        "title": "Ave Verum Corpus",
                        "composer": "Wolfgang Amadeus Mozart",
                        "catalogue": "KV 618",
                    },
                    "representation": {"provider": "imslp", "format": "musicxml", "confidence": 0.9},
                    "score": 0.9,
                    "evidence": [],
                }
            ],
        }
    ),
)
_SEARCH_GET_200 = _resp("Search retrieved", _SEARCH_CREATED_201["content"])
_JOB_CREATED_201 = _resp(
    "Job created",
    _example({"job_id": "job-1", "type": "provider-sync", "state": "completed", "progress": 100, "result": {}}),
)
_JOB_LIST_200 = _resp(
    "Jobs list",
    _example([{"job_id": "job-1", "type": "provider-sync", "state": "completed", "progress": 100, "result": {}}]),
)
_JOB_GET_200 = _resp("Job retrieved", _JOB_CREATED_201["content"])
_PROVIDER_LIST_200 = _resp(
    "Providers list",
    _example(
        [
            {
                "provider_id": "imslp",
                "name": "IMSLP",
                "available": True,
                "formats": ["musicxml", "pdf"],
                "last_sync": None,
            }
        ]
    ),
)
_PROVIDER_GET_200 = _resp(
    "Provider retrieved",
    _example(
        {
            "provider_id": "imslp",
            "name": "IMSLP",
            "available": True,
            "formats": ["musicxml", "pdf"],
            "last_sync": None,
        }
    ),
)
_KNOWLEDGE_OBSERVATIONS_200 = _resp(
    "Knowledge observations",
    _example(
        [
            {
                "execution_id": "e1",
                "source": "merge",
                "field": "title",
                "value": "Ave Verum K618",
                "provider": "imslp",
            }
        ]
    ),
)
_KNOWLEDGE_FACTS_200 = _resp(
    "Knowledge facts",
    _example([{"fact_type": "frequency", "field": "title", "value": "Ave Verum K618", "count": 2}]),
)
_KNOWLEDGE_SUGGESTIONS_200 = _resp(
    "Knowledge suggestions",
    _example(
        [
            {
                "suggestion_type": "add_alias",
                "field": "title",
                "source_value": "Ave Verum K618",
                "target_value": "Ave Verum Corpus KV 618",
                "reason": "observed 2 times",
            }
        ]
    ),
)
_HEALTH_200 = _resp("Health", _example({"status": "ok"}))
_READY_200 = _resp("Ready", _example({"status": "ready"}))
_LIVE_200 = _resp("Live", _example({"status": "live"}))
_VERSION_200 = _resp("Version", _example({"version": VERSION}))
_STATISTICS_200 = _resp(
    "Statistics",
    _example(
        {
            "providers": 5,
            "searches": 10,
            "jobs": 3,
            "knowledge_observations": 12,
            "knowledge_facts": 4,
            "knowledge_suggestions": 1,
        }
    ),
)
_SOURCES_LIST_200 = _resp(
    "Repository sources",
    _example(
        [
            {
                "source_id": "imslp",
                "name": "IMSLP",
                "type": "HTTP",
                "origin": "Official",
                "trust": "Verified",
                "status": "Online",
                "quality": 96,
                "quality_label": "Excellent",
                "updated_at": "2026-08-12 09:14 UTC",
            }
        ]
    ),
)
_SOURCE_GET_200 = _resp(
    "Repository source ficha",
    _example(
        {
            "source_id": "imslp",
            "name": "IMSLP",
            "type": "HTTP",
            "origin": "Official",
            "trust": "Verified",
            "status": "Online",
            "quality": 96,
            "quality_label": "Excellent",
            "updated_at": "2026-08-12 09:14 UTC",
            "representations": 128431,
            "works": 38912,
            "composers": 3281,
            "formats": ["MusicXML", "PDF", "MIDI"],
            "catalogues": ["BWV", "KV", "Hob.", "Op."],
            "duplicate_percent": 1.2,
            "coverage": ["Baroque", "Classical", "Romanticism"],
            "capabilities": ["Search", "Download", "MusicXML", "PDF", "MIDI", "Incremental Sync"],
            "description": "Official repository of public-domain scores.",
            "license": "Public Domain",
            "website": "https://imslp.org",
            "contact": "contact@imslp.org",
            "notes": "Very good Mozart coverage.",
            "observations": [{"date": "2026-07-18", "text": "Issues detected with Händel searches."}],
            "tags": ["Baroque", "Choral", "Public Domain"],
            "community_rating": 4,
            "reviews": 27,
            "searches": 3214,
            "downloads": 9321,
            "contributions": 42,
            "availability": 99.8,
        }
    ),
)


_UNAUTHORIZED_401 = _resp(
    "Unauthorized",
    _error("UNAUTHORIZED", "Missing or invalid access token"),
)
_FORBIDDEN_403 = _resp(
    "Forbidden",
    _error("FORBIDDEN", "Insufficient permissions"),
)
_SERVICE_UNAVAILABLE_503 = _resp(
    "Service unavailable",
    _error("SERVICE_UNAVAILABLE", "Service identity is not configured"),
)
_VOTE_201 = _resp(
    "Vote recorded",
    _example({"work_id": "w1", "vote": 5, "voted_at": "2026-08-06T10:00:00Z", "vote_day": "2026-08-06"}),
)
_DUPLICATE_VOTE_409 = _resp(
    "Duplicate vote",
    _error("DUPLICATE_VOTE", "Already voted for this work today"),
)
_INVALID_VOTE_422 = _resp(
    "Invalid vote",
    _error("INVALID_VOTE", "Vote must be between 1 and 5"),
)
_WORK_STATS_200 = _resp(
    "Work statistics",
    _example({"work_id": "w1", "vote_count": 37, "vote_average": 4.32}),
)
_COMPOSER_STATS_200 = _resp(
    "Composer statistics",
    _example({"composer_id": "mozart", "vote_count": 1523, "vote_average": 4.41}),
)


def _work_stats_dto(d: dict[str, object]) -> WorkStatisticsResponse:
    return WorkStatisticsResponse(
        work_id=cast("str", d["work_id"]),
        rating=cast("float | None", d.get("rating")),
        vote_count=cast("int", d["vote_count"]),
        work_count=cast("int", d.get("work_count") or 1),
    )


def _composer_stats_dto(d: dict[str, object]) -> ComposerStatisticsResponse:
    return ComposerStatisticsResponse(
        composer_id=cast("str", d["composer_id"]),
        rating=cast("float | None", d.get("rating")),
        vote_count=cast("int", d["vote_count"]),
        work_count=cast("int", d.get("work_count") or 0),
    )


def _composer_summary_dto(d: dict[str, object]) -> ComposerSummaryResponse:
    return ComposerSummaryResponse(
        id=cast("str", d.get("id") or ""),
        name=cast("str", d.get("name") or ""),
        status=cast("str", d.get("status") or "active"),
        aliases_count=cast("int", d.get("aliases_count") or 0),
        works_count=cast("int", d.get("works_count") or 0),
        review_status=cast("str | None", d.get("review_status")),
    )


def _composer_list_dto(d: dict[str, object]) -> ComposerListResponse:
    items = d.get("items")
    raw_items = items if isinstance(items, list) else []
    return ComposerListResponse(
        items=[_composer_summary_dto(dict(i)) for i in raw_items if isinstance(i, dict)],
        total=cast("int", d.get("total") or 0),
    )


def _composer_detail_dto(d: dict[str, object]) -> ComposerDetailResponse:
    aliases = d.get("aliases")
    raw_aliases = aliases if isinstance(aliases, list) else []
    evidence = d.get("creation_evidence")
    raw_evidence = evidence if isinstance(evidence, list) else []
    return ComposerDetailResponse(
        id=cast("str", d.get("id") or ""),
        name=cast("str", d.get("name") or ""),
        status=cast("str", d.get("status") or "active"),
        aliases=[str(a) for a in raw_aliases if isinstance(a, str)],
        works_count=cast("int", d.get("works_count") or 0),
        merged_into=cast("str | None", d.get("merged_into")),
        merged_at=_iso_or_none(d.get("merged_at")),
        creation_evidence=[_composer_evidence_dto(dict(e)) for e in raw_evidence if isinstance(e, dict)],
        review_status=cast("str | None", d.get("review_status")),
        reviewed_at=_iso_or_none(d.get("reviewed_at")),
    )


def _composer_evidence_dto(d: dict[str, object]) -> ComposerCreationEvidenceResponse:
    return ComposerCreationEvidenceResponse(
        composer_id=cast("str", d.get("composer_id") or ""),
        extracted_author=cast("str | None", d.get("extracted_author")),
        work_id=cast("int | None", d.get("work_id")),
        work_title=cast("str | None", d.get("work_title")),
        provider=cast("str | None", d.get("provider")),
        resource_reference=cast("str | None", d.get("resource_reference")),
    )


def _composer_works_dto(d: dict[str, object]) -> ComposerWorksResponse:
    items = d.get("items")
    raw_items = items if isinstance(items, list) else []
    return ComposerWorksResponse(
        items=[_composer_work_ref(dict(i)) for i in raw_items if isinstance(i, dict)],
        total=cast("int", d.get("total") or 0),
    )


def _composer_work_ref(d: dict[str, object]) -> ComposerWorkRefResponse:
    return ComposerWorkRefResponse(
        work_id=cast("int", d.get("work_id") or 0),
        title=cast("str | None", d.get("title")),
        composer_id=cast("str | None", d.get("composer_id")),
        tags=cast("str | None", d.get("tags")),
    )


def _merge_result_dto(d: dict[str, object]) -> MergeComposersResultResponse:
    sources = d.get("sources_merged")
    raw_sources = sources if isinstance(sources, list) else []
    return MergeComposersResultResponse(
        target_id=cast("str", d.get("target_id") or ""),
        sources_merged=[str(s) for s in raw_sources if isinstance(s, str)],
        aliases_transferred=cast("int", d.get("aliases_transferred") or 0),
        works_moved=cast("int", d.get("works_moved") or 0),
        merge_operation_id=cast("str | None", d.get("merge_operation_id")),
    )


def _iso_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _standard_errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    by_code: dict[int | str, dict[str, Any]] = {
        422: _VALIDATION_422,
        500: _INTERNAL_500,
    }
    for code in codes:
        if code == 400:
            by_code[400] = _INVALID_QUERY_400
        elif code == 404:
            by_code[404] = _NOT_FOUND_404
    return by_code


def create_platform_app(
    container: Container | None = None,
    knowledge: KnowledgeStore | None = None,
) -> FastAPI:
    """Build the OSAP Platform API (V3.1) over application services."""
    container = container or wire(Container())
    api = PlatformApi(container, knowledge)
    _configure_osap_logging()
    app = FastAPI(
        title="OSAP REST API",
        description="Public REST API of OSAP (V3.1). Exposes the domain as use cases; never internal components.",
        version="3.1",
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        contact={"name": "OSAP", "url": "https://example.com", "email": "osap@example.com"},
        openapi_tags=_TAGS,
    )

    def ok(data: object) -> SuccessEnvelope[object]:
        return SuccessEnvelope(success=True, request_id=_request_id(), data=data)

    def fail(status: int, response: Response, code: str, message: str) -> ErrorEnvelope:
        response.status_code = status
        return ErrorEnvelope(
            success=False,
            request_id=_request_id(),
            error=ErrorBody(code=code, message=message),
        )

    @app.get(
        "/api/v1/representations/{representation_id}/download",
        tags=["Searches"],
        summary="Download a representation",
        description=(
            "Streams the representation file. Por defecto fuerza descarga (attachment). "
            "Con `?view=1` sirve el fichero inline con su content-type para visualizarlo "
            "directamente en el navegador (p. ej. PDFs)."
        ),
        response_model=None,
    )
    def download_representation(
        representation_id: str,
        response: Response,
        view: int = Query(default=0, ge=0, le=1),
    ) -> Response | ErrorEnvelope:
        info = api.get_representation_download(representation_id)
        if info is None:
            return fail(404, response, "NOT_FOUND", "Representation not found")
        url = str(info.get("download_url") or "")
        if not url:
            return fail(404, response, "NOT_FOUND", "No download available")
        filename = _download_filename(info)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpenMusicRepository download)"})

        def iter_chunks() -> Iterator[bytes]:
            with urllib.request.urlopen(request, timeout=30) as source:  # noqa: S310 (trusted storage)
                while True:
                    chunk = source.read(65536)
                    if not chunk:
                        break
                    yield chunk

        media_type = "application/octet-stream"
        disposition = f'attachment; filename="{filename}"'
        if view == 1:
            media_type = _media_type_for_format(str(info.get("format") or ""))
            disposition = f'inline; filename="{filename}"'

        return StreamingResponse(
            iter_chunks(),
            headers={"Content-Disposition": disposition},
            media_type=media_type,
        )

    # --- search model (Search Studio is driven by it) ------------------------

    @app.get(
        "/api/v1/search-model",
        tags=["Searches"],
        summary="Search model",
        description="Exposes the search criteria/blocks that Search Studio renders.",
        response_model=SuccessEnvelope[SearchModel],
        responses={200: _resp("Search model", _example({}))},
    )
    def search_model() -> SuccessEnvelope[object]:
        return ok(api.search_model())

    @app.get(
        "/api/v1/intent",
        tags=["Searches"],
        summary="Intent detection",
        description="Classifies a query into an entity (composer, work, catalogue, collection, source).",
        response_model=SuccessEnvelope[IntentResponse],
        responses={200: _resp("Intent", _example({"type": "composer", "label": "Mozart"}))},
    )
    def detect_intent(query: str = "") -> SuccessEnvelope[object]:
        return ok(api.detect_intent(query))

    # --- searches -----------------------------------------------------------

    @app.post(
        "/api/v1/searches",
        status_code=201,
        tags=["Searches"],
        summary="Create a search",
        description="Creates a search as a resource. Returns 201 with a Location header.",
        response_model=SuccessEnvelope[SearchResponse] | ErrorEnvelope,
        responses={201: _SEARCH_CREATED_201, **_standard_errors(400)},
    )
    def create_search(
        payload: SearchRequest, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        del authorization  # auth prepared but disabled in V3.1
        has_query = bool(payload.query and payload.query.strip())
        if not has_query and not payload.composer and not payload.title and not payload.catalogue:
            return fail(400, response, "INVALID_QUERY", "Query cannot be empty")
        search_id, search = api.create_search(payload)
        response.headers["Location"] = f"/api/v1/searches/{search_id}"
        return ok(search)

    @app.get(
        "/api/v1/searches/{search_id}",
        tags=["Searches"],
        summary="Get a search",
        description="Retrieves the result of a previously created search.",
        response_model=SuccessEnvelope[SearchResponse] | ErrorEnvelope,
        responses={200: _SEARCH_GET_200, **_standard_errors(404)},
    )
    def get_search(search_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        search = api.get_search(search_id)
        if search is None:
            return fail(404, response, "NOT_FOUND", "Search not found")
        return ok(search)

    # --- jobs ---------------------------------------------------------------

    @app.post(
        "/api/v1/jobs",
        status_code=201,
        tags=["Jobs"],
        summary="Create a job",
        description="Creates a job of the given type (e.g. provider-sync).",
        response_model=SuccessEnvelope[JobResponse] | ErrorEnvelope,
        responses={201: _JOB_CREATED_201, **_standard_errors(400)},
    )
    def create_job(
        payload: JobCreateRequest, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        del authorization  # auth prepared but disabled in V3.1
        if not payload.type.strip():
            return fail(400, response, "INVALID_JOB_TYPE", "Job type cannot be empty")
        job = api.create_job(payload.type)
        response.headers["Location"] = f"/api/v1/jobs/{job.job_id}"
        return ok(job)

    @app.get(
        "/api/v1/jobs",
        tags=["Jobs"],
        summary="List jobs",
        description="Lists all jobs.",
        response_model=SuccessEnvelope[list[JobResponse]],
        responses={200: _JOB_LIST_200, **_standard_errors()},
    )
    def list_jobs() -> SuccessEnvelope[object]:
        return ok(api.list_jobs())

    @app.get(
        "/api/v1/jobs/{job_id}",
        tags=["Jobs"],
        summary="Get a job",
        description="Retrieves a single job by id.",
        response_model=SuccessEnvelope[JobResponse] | ErrorEnvelope,
        responses={200: _JOB_GET_200, **_standard_errors(404)},
    )
    def get_job(job_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        job = api.get_job(job_id)
        if job is None:
            return fail(404, response, "NOT_FOUND", "Job not found")
        return ok(job)

    # --- providers ----------------------------------------------------------

    @app.get(
        "/api/v1/providers",
        tags=["Providers"],
        summary="List providers",
        description="Lists provider state and capabilities.",
        response_model=SuccessEnvelope[list[ProviderResponse]],
        responses={200: _PROVIDER_LIST_200, **_standard_errors()},
    )
    def list_providers() -> SuccessEnvelope[object]:
        return ok(api.list_providers())

    @app.get(
        "/api/v1/providers/{provider_id}",
        tags=["Providers"],
        summary="Get a provider",
        description="Retrieves a single provider.",
        response_model=SuccessEnvelope[ProviderResponse] | ErrorEnvelope,
        responses={200: _PROVIDER_GET_200, **_standard_errors(404)},
    )
    def get_provider(provider_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        provider = api.get_provider(provider_id)
        if provider is None:
            return fail(404, response, "NOT_FOUND", "Provider not found")
        return ok(provider)

    @app.get(
        "/api/v1/providers/{provider_id}/status",
        tags=["Providers"],
        summary="Provider status",
        description="Retrieves provider status.",
        response_model=SuccessEnvelope[ProviderResponse] | ErrorEnvelope,
        responses={200: _PROVIDER_GET_200, **_standard_errors(404)},
    )
    def provider_status(provider_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        provider = api.get_provider(provider_id)
        if provider is None:
            return fail(404, response, "NOT_FOUND", "Provider not found")
        return ok(provider)

    # --- repository sources (Source Catalog) ---------------------------------

    @app.get(
        "/api/v1/repository-sources",
        tags=["Sources"],
        summary="List repository sources",
        description="Lists the permanent source catalog.",
        response_model=SuccessEnvelope[list[RepositorySourceSummary]],
        responses={200: _SOURCES_LIST_200, **_standard_errors()},
    )
    def list_repository_sources() -> SuccessEnvelope[object]:
        return ok(api.list_repository_sources())

    @app.get(
        "/api/v1/repository-sources/{source_id}",
        tags=["Sources"],
        summary="Get a repository source",
        description="Retrieves the full catalog ficha of a repository source.",
        response_model=SuccessEnvelope[RepositorySource] | ErrorEnvelope,
        responses={200: _SOURCE_GET_200, **_standard_errors(404)},
    )
    def get_repository_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = api.get_repository_source(source_id)
        if source is None:
            return fail(404, response, "NOT_FOUND", "Repository source not found")
        return ok(source)

    # --- session sources (user's temporary sources) -------------------------

    @app.post(
        "/api/v1/sources",
        status_code=201,
        tags=["Sources"],
        summary="Add a source",
        description="Creates a temporary (Session) source for the current search/session.",
        response_model=SuccessEnvelope[SessionSource],
        responses={
            201: _resp(
                "Source created",
                _example(
                    {
                        "source_id": "src-1",
                        "name": "My folder",
                        "type": "Local",
                        "location": "/path",
                        "status": "CREATED",
                        "created_at": "...",
                    }
                ),
            )
        },
    )
    def create_source(payload: SessionSourceCreate) -> SuccessEnvelope[object]:
        source = api.create_session_source(payload.name, payload.type, payload.location)
        return ok(source)

    @app.get(
        "/api/v1/sources",
        tags=["Sources"],
        summary="List session sources",
        description="Lists the user's temporary sources.",
        response_model=SuccessEnvelope[list[SessionSource]],
        responses={200: _resp("Session sources", _example([]))},
    )
    def list_sources() -> SuccessEnvelope[object]:
        return ok(api.list_session_sources())

    @app.get(
        "/api/v1/sources/{source_id}",
        tags=["Sources"],
        summary="Get a session source",
        description="Retrieves a user's temporary source.",
        response_model=SuccessEnvelope[SessionSource] | ErrorEnvelope,
        responses={200: _resp("Session source", _example({})), **_standard_errors(404)},
    )
    def get_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = api.get_session_source(source_id)
        if source is None:
            return fail(404, response, "NOT_FOUND", "Session source not found")
        return ok(source)

    @app.delete(
        "/api/v1/sources/{source_id}",
        tags=["Sources"],
        summary="Forget a session source",
        description="Removes a user's temporary source.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={200: _resp("Forget", _example(True)), **_standard_errors(404)},
    )
    def forget_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        if not api.forget_session_source(source_id):
            return fail(404, response, "NOT_FOUND", "Session source not found")
        return ok(True)

    @app.post(
        "/api/v1/sources/{source_id}/analyze",
        tags=["Sources"],
        summary="Analyze a session source",
        description="Runs automatic analysis on a temporary source.",
        response_model=SuccessEnvelope[SessionSource] | ErrorEnvelope,
        responses={200: _resp("Analyzed", _example({})), **_standard_errors(404)},
    )
    def analyze_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = api.analyze_session_source(source_id)
        if source is None:
            return fail(404, response, "NOT_FOUND", "Session source not found")
        return ok(source)

    @app.post(
        "/api/v1/sources/{source_id}/use",
        tags=["Sources"],
        summary="Use a session source",
        description="Uses a temporary source in the current search/session.",
        response_model=SuccessEnvelope[SessionSource] | ErrorEnvelope,
        responses={200: _resp("Used", _example({})), **_standard_errors(404)},
    )
    def use_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = api.use_session_source(source_id)
        if source is None:
            return fail(404, response, "NOT_FOUND", "Session source not found")
        return ok(source)

    # --- discovery ----------------------------------------------------------

    @app.get(
        "/api/v1/discover/sources",
        tags=["Sources"],
        summary="Discover sources",
        description="Suggestions of new sources (discovery catalog).",
        response_model=SuccessEnvelope[list[DiscoverSource]],
        responses={200: _resp("Discover", _example([]))},
    )
    def discover_sources() -> SuccessEnvelope[object]:
        return ok(api.discover_sources())

    # --- knowledge (read-only) ----------------------------------------------

    @app.get(
        "/api/v1/knowledge/observations",
        tags=["Knowledge"],
        summary="Knowledge observations",
        description="Lists knowledge observations (read-only).",
        response_model=SuccessEnvelope[list[KnowledgeObservationDTO]],
        responses={200: _KNOWLEDGE_OBSERVATIONS_200, **_standard_errors()},
    )
    def knowledge_observations() -> SuccessEnvelope[object]:
        return ok(api.knowledge().observations)

    @app.get(
        "/api/v1/knowledge/facts",
        tags=["Knowledge"],
        summary="Knowledge facts",
        description="Lists knowledge facts (read-only).",
        response_model=SuccessEnvelope[list[KnowledgeFactDTO]],
        responses={200: _KNOWLEDGE_FACTS_200, **_standard_errors()},
    )
    def knowledge_facts() -> SuccessEnvelope[object]:
        return ok(api.knowledge().facts)

    @app.get(
        "/api/v1/knowledge/suggestions",
        tags=["Knowledge"],
        summary="Knowledge suggestions",
        description="Lists knowledge suggestions (read-only).",
        response_model=SuccessEnvelope[list[KnowledgeSuggestionDTO]],
        responses={200: _KNOWLEDGE_SUGGESTIONS_200, **_standard_errors()},
    )
    def knowledge_suggestions() -> SuccessEnvelope[object]:
        return ok(api.knowledge().suggestions)

    # --- system -------------------------------------------------------------

    @app.get(
        "/api/v1/system/health",
        tags=["System"],
        summary="Health",
        description="Liveness and overall health.",
        response_model=SuccessEnvelope[SystemHealthResponse],
        responses={200: _HEALTH_200, **_standard_errors()},
    )
    def system_health() -> SuccessEnvelope[object]:
        return ok(SystemHealthResponse(status=api.health()))

    @app.get(
        "/api/v1/system/ready",
        tags=["System"],
        summary="Ready",
        description="Readiness probe.",
        response_model=SuccessEnvelope[SystemHealthResponse],
        responses={200: _READY_200, **_standard_errors()},
    )
    def system_ready() -> SuccessEnvelope[object]:
        return ok(SystemHealthResponse(status="ready"))

    @app.get(
        "/api/v1/system/live",
        tags=["System"],
        summary="Live",
        description="Liveness probe.",
        response_model=SuccessEnvelope[SystemHealthResponse],
        responses={200: _LIVE_200, **_standard_errors()},
    )
    def system_live() -> SuccessEnvelope[object]:
        return ok(SystemHealthResponse(status="live"))

    @app.get(
        "/api/v1/system/version",
        tags=["System"],
        summary="Version",
        description="OSAP API version.",
        response_model=SuccessEnvelope[SystemVersionResponse],
        responses={200: _VERSION_200, **_standard_errors()},
    )
    def system_version() -> SuccessEnvelope[object]:
        return ok(api.version())

    @app.get(
        "/api/v1/system/statistics",
        tags=["System"],
        summary="Statistics",
        description="System statistics.",
        response_model=SuccessEnvelope[SystemStatisticsResponse],
        responses={200: _STATISTICS_200, **_standard_errors()},
    )
    def system_statistics() -> SuccessEnvelope[object]:
        return ok(api.statistics())

    # --- votes & statistics (v1) --------------------------------------------

    @app.post(
        "/api/v1/works/{work_id}/vote",
        status_code=201,
        tags=["Votes"],
        summary="Vote a work",
        description="Registers a 1..5 vote for a work. Requires authentication; one vote per work and UTC day.",
        response_model=SuccessEnvelope[VoteResponse] | ErrorEnvelope,
        responses={
            201: _VOTE_201,
            401: _UNAUTHORIZED_401,
            403: _FORBIDDEN_403,
            404: _NOT_FOUND_404,
            409: _DUPLICATE_VOTE_409,
            **_standard_errors(422),
        },
    )
    def cast_work_vote(
        work_id: str,
        payload: VoteRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            api.require_can_vote(authorization)
            vote = api.cast_vote(authorization, work_id, payload.vote)
        except UnauthenticatedError:
            return fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return fail(403, response, "FORBIDDEN", "A verified user role is required to vote")
        except InvalidVoteError:
            return fail(422, response, "INVALID_VOTE", "Vote must be between 1 and 5")
        except WorkNotFoundError:
            return fail(404, response, "NOT_FOUND", "Work not found")
        except DuplicateVoteError:
            return fail(409, response, "DUPLICATE_VOTE", "Already voted for this work today")
        return ok(
            VoteResponse(
                work_id=vote.work_id,
                vote=vote.vote,
                voted_at=vote.voted_at.isoformat() if vote.voted_at else "",
                vote_day=vote.vote_day or "",
            )
        )

    @app.get(
        "/api/v1/works/{work_id}/statistics",
        tags=["Votes"],
        summary="Work statistics",
        description="Valoración agregada de una obra (proxy de osap-storage).",
        response_model=SuccessEnvelope[WorkStatisticsResponse] | ErrorEnvelope,
        responses={200: _WORK_STATS_200, 404: _NOT_FOUND_404, 503: _SERVICE_UNAVAILABLE_503, **_standard_errors()},
    )
    def work_statistics(work_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            stats = api.work_statistics(work_id)
        except WorkNotFoundError:
            return fail(404, response, "NOT_FOUND", "Work not found")
        except StorageUnavailableError:
            return fail(503, response, "SERVICE_UNAVAILABLE", "Statistics service is not configured")
        return ok(
            WorkStatisticsResponse(
                work_id=stats.work_id,
                rating=stats.rating,
                adjusted_rating=stats.adjusted_rating,
                vote_count=stats.vote_count,
                work_count=stats.work_count,
                confidence=stats.confidence,
                calculated_at=stats.calculated_at.isoformat() if stats.calculated_at else None,
            )
        )

    @app.get(
        "/api/v1/composers/{composer_id}/statistics",
        tags=["Votes"],
        summary="Composer statistics",
        description="Valoración agregada de un compositor (proxy de osap-storage).",
        response_model=SuccessEnvelope[ComposerStatisticsResponse] | ErrorEnvelope,
        responses={200: _COMPOSER_STATS_200, 404: _NOT_FOUND_404, 503: _SERVICE_UNAVAILABLE_503, **_standard_errors()},
    )
    def composer_statistics(composer_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            stats = api.composer_statistics(composer_id)
        except WorkNotFoundError:
            return fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageUnavailableError:
            return fail(503, response, "SERVICE_UNAVAILABLE", "Statistics service is not configured")
        return ok(
            ComposerStatisticsResponse(
                composer_id=stats.composer_id,
                rating=stats.rating,
                adjusted_rating=stats.adjusted_rating,
                vote_count=stats.vote_count,
                work_count=stats.work_count,
                confidence=stats.confidence,
                calculated_at=stats.calculated_at.isoformat() if stats.calculated_at else None,
            )
        )

    @app.get(
        "/api/v1/admin/votes",
        tags=["Votes"],
        summary="Votes overview (admin)",
        description="Admin overview: total votes, top works, top composers and last execution.",
        response_model=SuccessEnvelope[VotesOverviewResponse] | ErrorEnvelope,
        responses={200: _resp("Votes overview", _example({})), 401: _UNAUTHORIZED_401, 403: _FORBIDDEN_403},
    )
    def admin_votes(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            api.require_admin(authorization)
        except UnauthenticatedError:
            return fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return fail(403, response, "FORBIDDEN", "Admin role required")
        try:
            overview = api.votes_overview()
        except StorageUnavailableError:
            return fail(503, response, "SERVICE_UNAVAILABLE", "Votes service is not configured")
        top_works = cast("list[dict[str, object]]", overview["top_works"])
        top_composers = cast("list[dict[str, object]]", overview["top_composers"])
        return ok(
            VotesOverviewResponse(
                total_votes=int(cast("int", overview["total_votes"])),
                top_works=[_work_stats_dto(w) for w in top_works],
                top_composers=[_composer_stats_dto(c) for c in top_composers],
                last_execution=cast("dict[str, object] | None", overview["last_execution"]),
            )
        )

    # --- registro / verificación de usuario (proxy a osap-auth) --------------

    @app.post(
        "/api/v1/auth/register",
        status_code=200,
        tags=["Auth"],
        summary="Register user",
        description="Registra un usuario vía osap-auth (proxy público, sin service client). "
        "Anti-enumeración: email ya existente devuelve la misma respuesta genérica.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _resp("Register result", _example({})),
            422: _INVALID_VOTE_422,
            429: _resp("Rate limited", _error("RATE_LIMITED", "Too many requests")),
            502: _resp("Bad gateway", _error("BAD_GATEWAY", "Identity service unreachable")),
            **_standard_errors(),
        },
    )
    def register_user(
        payload: RegisterRequest,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            status, doc = api.register_user(payload.email, payload.password, payload.name)
        except AuthProxyError:
            return fail(502, response, "BAD_GATEWAY", "Identity service unreachable")
        if status == 422:
            return fail(422, response, "VALIDATION_ERROR", "Invalid email/password/name")
        if status == 429:
            return fail(429, response, "RATE_LIMITED", "Too many requests")
        if status >= 500:
            return fail(502, response, "BAD_GATEWAY", "Identity service unavailable")
        return ok(doc)

    @app.post(
        "/api/v1/auth/verify-email",
        status_code=200,
        tags=["Auth"],
        summary="Verify email",
        description="Verifica el email de un usuario vía osap-auth (proxy público).",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _resp("Email verified", _example({})),
            422: _INVALID_VOTE_422,
            502: _resp("Bad gateway", _error("BAD_GATEWAY", "Identity service unreachable")),
            **_standard_errors(),
        },
    )
    def verify_email(payload: VerifyEmailRequest, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            status, doc = api.verify_email(payload.token)
        except AuthProxyError:
            return fail(502, response, "BAD_GATEWAY", "Identity service unreachable")
        if status == 422:
            return fail(422, response, "VALIDATION_ERROR", "Invalid token")
        if status >= 500:
            return fail(502, response, "BAD_GATEWAY", "Identity service unavailable")
        return ok(doc)

    # --- compositores (consulta pública + fusión admin) ----------------------

    @app.get(
        "/api/v1/works/{work_id}",
        tags=["Composers"],
        summary="Work detail (inspection)",
        description="Detalle completo de una obra (work + resources) para inspección administrativa.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _resp("Work detail", _example({})),
            404: _NOT_FOUND_404,
            503: _SERVICE_UNAVAILABLE_503,
            **_standard_errors(),
        },
    )
    def get_work(work_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            doc = api.get_work(work_id)
        except StorageUnavailableError:
            return fail(503, response, "SERVICE_UNAVAILABLE", "Works service is not configured")
        if doc is None:
            return fail(404, response, "NOT_FOUND", "Work not found")
        return ok(doc)

    @app.get(
        "/api/v1/composers",
        tags=["Composers"],
        summary="List composers",
        description="Consulta pública de compositores (listado, q, paginado). Backend: osap-storage con storage:read.",
        response_model=SuccessEnvelope[ComposerListResponse] | ErrorEnvelope,
        responses={200: _resp("Composers list", _example({})), 503: _SERVICE_UNAVAILABLE_503, **_standard_errors()},
    )
    def list_composers(
        response: Response,
        q: str | None = Query(default=None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        review: str | None = Query(
            default=None,
            pattern=r"^(correct|incorrect|reviewed|not_reviewed)$",
            description="Filtro por estado de revisión.",
        ),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ok(_composer_list_dto(api.list_composers(q, limit, offset, review)))
        except StorageComposerError:
            return fail(503, response, "SERVICE_UNAVAILABLE", "Composer service is not configured")

    @app.get(
        "/api/v1/composers/{composer_id}",
        tags=["Composers"],
        summary="Composer detail",
        description="Detalle de un compositor. Backend: osap-storage con storage:read.",
        response_model=SuccessEnvelope[ComposerDetailResponse] | ErrorEnvelope,
        responses={200: _resp("Composer detail", _example({})), 404: _NOT_FOUND_404, **_standard_errors()},
    )
    def get_composer(composer_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            detail = api.get_composer(composer_id)
        except StorageComposerError:
            return fail(503, response, "SERVICE_UNAVAILABLE", "Composer service is not configured")
        if detail is None:
            return fail(404, response, "NOT_FOUND", "Composer not found")
        return ok(_composer_detail_dto(detail))

    @app.get(
        "/api/v1/composers/{composer_id}/works",
        tags=["Composers"],
        summary="Composer works",
        description="Obras de un compositor. Backend: osap-storage con storage:read.",
        response_model=SuccessEnvelope[ComposerWorksResponse] | ErrorEnvelope,
        responses={200: _resp("Composer works", _example({})), 503: _SERVICE_UNAVAILABLE_503, **_standard_errors()},
    )
    def composer_works(
        response: Response,
        composer_id: str,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ok(_composer_works_dto(api.composer_works(composer_id, limit, offset)))
        except StorageComposerError:
            return fail(503, response, "SERVICE_UNAVAILABLE", "Composer service is not configured")

    @app.post(
        "/api/v1/admin/composers/merge",
        status_code=200,
        tags=["Composers"],
        summary="Merge composers (admin)",
        description="Fusiona `sources` dentro de `target_id` (ambos composer_id existentes). "
        "Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[MergeComposersResultResponse] | ErrorEnvelope,
        responses={
            200: _resp("Merge result", _example({})),
            401: _UNAUTHORIZED_401,
            403: _FORBIDDEN_403,
            404: _NOT_FOUND_404,
            **_standard_errors(422),
        },
    )
    def merge_composers(
        payload: MergeComposersRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            result = api.merge_composers(authorization, payload.target_id, payload.sources)
        except UnauthenticatedError:
            return fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageComposerError:
            return fail(
                503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured"
            )
        return ok(_merge_result_dto(result))

    @app.post(
        "/api/v1/admin/composers",
        status_code=201,
        tags=["Composers"],
        summary="Create composer (admin)",
        description="Crea un compositor con el nombre dado (para fusionar hacia un compositor "
        "inexistente). Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[ComposerSummaryResponse] | ErrorEnvelope,
        responses={
            201: _resp("Created composer", _example({})),
            401: _UNAUTHORIZED_401,
            403: _FORBIDDEN_403,
            **_standard_errors(422),
        },
    )
    def create_composer(
        payload: CreateComposerRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            composer = api.create_composer(authorization, payload.name)
        except UnauthenticatedError:
            return fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return fail(403, response, "FORBIDDEN", "Admin role required")
        except StorageComposerError:
            return fail(
                503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured"
            )
        return ok(_composer_summary_dto(composer))

    @app.post(
        "/api/v1/admin/composers/{composer_id}/review",
        status_code=200,
        tags=["Composers"],
        summary="Set composer review status (admin)",
        description="Marca el estado de revisión de un compositor (correct|incorrect|reviewed|"
        "not_reviewed). Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[ComposerDetailResponse] | ErrorEnvelope,
        responses={
            200: _resp("Reviewed composer", _example({})),
            401: _UNAUTHORIZED_401,
            403: _FORBIDDEN_403,
            404: _NOT_FOUND_404,
            **_standard_errors(422),
        },
    )
    def review_composer(
        composer_id: str,
        payload: ReviewComposerRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            composer = api.review_composer(authorization, composer_id, payload.review_status)
        except UnauthenticatedError:
            return fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageComposerError:
            return fail(
                503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured"
            )
        return ok(_composer_detail_dto(composer))

    return app
