"""V3.1 — OSAP Platform API (FastAPI HTTP adapter).

Thin HTTP layer over `PlatformApi` (Application API). It only serializes/validates the
public contract DTOs and returns the uniform envelope. It never talks to the domain
directly. Auth is prepared (Bearer) but disabled in V3.1.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import FastAPI, Header, Response

from src.osap.api.contracts import (
    ErrorBody,
    ErrorEnvelope,
    JobCreateRequest,
    SearchRequest,
    SuccessEnvelope,
    SystemHealthResponse,
)
from src.osap.api.platform import VERSION, PlatformApi
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire

if TYPE_CHECKING:
    from src.osap.api.platform import KnowledgeStore


def _request_id() -> str:
    return uuid.uuid4().hex


def create_platform_app(
    container: Container | None = None,
    knowledge: KnowledgeStore | None = None,
) -> FastAPI:
    """Build the OSAP Platform API (V3.1) over application services."""
    container = container or wire(Container())
    api = PlatformApi(container, knowledge)
    app = FastAPI(title="OSAP Platform API", version=VERSION, description="OSAP V3.1 public API")

    def ok(data: object) -> SuccessEnvelope:
        return SuccessEnvelope(success=True, request_id=_request_id(), data=data)

    def fail(status: int, response: Response, code: str, message: str) -> ErrorEnvelope:
        response.status_code = status
        return ErrorEnvelope(
            success=False,
            request_id=_request_id(),
            error=ErrorBody(code=code, message=message),
        )

    # --- searches -----------------------------------------------------------

    @app.post("/api/v1/searches", status_code=201)
    def create_search(
        payload: SearchRequest, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope | ErrorEnvelope:
        del authorization  # auth prepared but disabled in V3.1
        if not payload.query.strip():
            return fail(400, response, "INVALID_QUERY", "Query cannot be empty")
        search_id, search = api.create_search(payload.query, payload.limit)
        response.headers["Location"] = f"/api/v1/searches/{search_id}"
        return ok(search)

    @app.get("/api/v1/searches/{search_id}")
    def get_search(search_id: str, response: Response) -> SuccessEnvelope | ErrorEnvelope:
        search = api.get_search(search_id)
        if search is None:
            return fail(404, response, "NOT_FOUND", "Search not found")
        return ok(search)

    # --- jobs ---------------------------------------------------------------

    @app.post("/api/v1/jobs", status_code=201)
    def create_job(
        payload: JobCreateRequest, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope | ErrorEnvelope:
        del authorization  # auth prepared but disabled in V3.1
        if not payload.type.strip():
            return fail(400, response, "INVALID_JOB_TYPE", "Job type cannot be empty")
        job = api.create_job(payload.type)
        response.headers["Location"] = f"/api/v1/jobs/{job.job_id}"
        return ok(job)

    @app.get("/api/v1/jobs")
    def list_jobs() -> SuccessEnvelope:
        return ok(api.list_jobs())

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str, response: Response) -> SuccessEnvelope | ErrorEnvelope:
        job = api.get_job(job_id)
        if job is None:
            return fail(404, response, "NOT_FOUND", "Job not found")
        return ok(job)

    # --- providers ----------------------------------------------------------

    @app.get("/api/v1/providers")
    def list_providers() -> SuccessEnvelope:
        return ok(api.list_providers())

    @app.get("/api/v1/providers/{provider_id}")
    def get_provider(provider_id: str, response: Response) -> SuccessEnvelope | ErrorEnvelope:
        provider = api.get_provider(provider_id)
        if provider is None:
            return fail(404, response, "NOT_FOUND", "Provider not found")
        return ok(provider)

    @app.get("/api/v1/providers/{provider_id}/status")
    def provider_status(provider_id: str, response: Response) -> SuccessEnvelope | ErrorEnvelope:
        provider = api.get_provider(provider_id)
        if provider is None:
            return fail(404, response, "NOT_FOUND", "Provider not found")
        return ok(provider)

    # --- knowledge (read-only) ----------------------------------------------

    @app.get("/api/v1/knowledge/observations")
    def knowledge_observations() -> SuccessEnvelope:
        return ok(api.knowledge().observations)

    @app.get("/api/v1/knowledge/facts")
    def knowledge_facts() -> SuccessEnvelope:
        return ok(api.knowledge().facts)

    @app.get("/api/v1/knowledge/suggestions")
    def knowledge_suggestions() -> SuccessEnvelope:
        return ok(api.knowledge().suggestions)

    # --- system -------------------------------------------------------------

    @app.get("/api/v1/system/health")
    def system_health() -> SuccessEnvelope:
        return ok(SystemHealthResponse(status=api.health()))

    @app.get("/api/v1/system/ready")
    def system_ready() -> SuccessEnvelope:
        return ok(SystemHealthResponse(status="ready"))

    @app.get("/api/v1/system/live")
    def system_live() -> SuccessEnvelope:
        return ok(SystemHealthResponse(status="live"))

    @app.get("/api/v1/system/version")
    def system_version() -> SuccessEnvelope:
        return ok(api.version())

    @app.get("/api/v1/system/statistics")
    def system_statistics() -> SuccessEnvelope:
        return ok(api.statistics())

    return app
