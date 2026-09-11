"""Router de jobs: create/list/get (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Response

from src.osap.api.contracts import (
    ErrorEnvelope,
    JobCreateRequest,
    JobResponse,
    SuccessEnvelope,
)

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_jobs_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.post(
        "/api/v1/jobs",
        status_code=201,
        tags=["Jobs"],
        summary="Create a job",
        description="Creates a job of the given type (e.g. provider-sync).",
        response_model=SuccessEnvelope[JobResponse] | ErrorEnvelope,
        responses={201: _shared._JOB_CREATED_201, **_shared._standard_errors(400)},
    )
    def create_job(
        payload: JobCreateRequest, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        del authorization  # auth prepared but disabled in V3.1
        # V3.2: el endpoint de jobs no está implementado. Antes devolvía un `DefaultJob`
        # no-op marcado como completed sin ejecutar trabajo; eso simulaba una ejecución
        # real. Se prefiere un 501 explícito a un falso positivo.
        return ctx.fail(
            501,
            response,
            "NOT_IMPLEMENTED",
            "Job execution is not implemented yet",
        )

    @router.get(
        "/api/v1/jobs",
        tags=["Jobs"],
        summary="List jobs",
        description="Lists all jobs.",
        response_model=SuccessEnvelope[list[JobResponse]],
        responses={200: _shared._JOB_LIST_200, **_shared._standard_errors()},
    )
    def list_jobs() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.list_jobs())

    @router.get(
        "/api/v1/jobs/{job_id}",
        tags=["Jobs"],
        summary="Get a job",
        description="Retrieves a single job by id.",
        response_model=SuccessEnvelope[JobResponse] | ErrorEnvelope,
        responses={200: _shared._JOB_GET_200, **_shared._standard_errors(404)},
    )
    def get_job(job_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        job = ctx.api.get_job(job_id)
        if job is None:
            return ctx.fail(404, response, "NOT_FOUND", "Job not found")
        return ctx.ok(job)

    return router
