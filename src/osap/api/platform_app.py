"""V3.1 — OSAP Platform API (FastAPI HTTP adapter).

Thin HTTP layer over `PlatformApi` (Application API). It only serializes/validates the
public contract DTOs and returns the uniform envelope. It never talks to the domain
directly. Auth is prepared (Bearer) but disabled in V3.1.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Header, Response

from src.osap.api.contracts import (
    ErrorBody,
    ErrorEnvelope,
    JobCreateRequest,
    JobResponse,
    KnowledgeFactDTO,
    KnowledgeObservationDTO,
    KnowledgeSuggestionDTO,
    ProviderResponse,
    SearchRequest,
    SearchResponse,
    SuccessEnvelope,
    SystemHealthResponse,
    SystemStatisticsResponse,
    SystemVersionResponse,
)
from src.osap.api.platform import VERSION, PlatformApi
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire

if TYPE_CHECKING:
    from src.osap.api.platform import KnowledgeStore

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
        if not payload.query.strip():
            return fail(400, response, "INVALID_QUERY", "Query cannot be empty")
        search_id, search = api.create_search(payload.query, payload.limit)
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
