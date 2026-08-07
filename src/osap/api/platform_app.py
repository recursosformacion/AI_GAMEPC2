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
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Header, Response
from fastapi.responses import StreamingResponse

from src.osap.api.contracts import (
    DiscoverSource,
    ErrorBody,
    ErrorEnvelope,
    IntentResponse,
    JobCreateRequest,
    JobResponse,
    KnowledgeFactDTO,
    KnowledgeObservationDTO,
    KnowledgeSuggestionDTO,
    ProviderResponse,
    RepositorySource,
    RepositorySourceSummary,
    SearchModel,
    SearchRequest,
    SearchResponse,
    SessionSource,
    SessionSourceCreate,
    SuccessEnvelope,
    SystemHealthResponse,
    SystemStatisticsResponse,
    SystemVersionResponse,
)
from src.osap.api.platform import VERSION, PlatformApi
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire

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
            "Streams the representation file with a Content-Disposition filename "
            "(the client never sees the storage URL)."
        ),
        response_model=None,
    )
    def download_representation(representation_id: str, response: Response) -> Response | ErrorEnvelope:
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

        return StreamingResponse(
            iter_chunks(),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
            media_type="application/octet-stream",
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

    return app
