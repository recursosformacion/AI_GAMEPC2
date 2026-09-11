"""Router de system: health/ready/live/version/statistics (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from src.osap.api.contracts import (
    SuccessEnvelope,
    SystemHealthResponse,
    SystemStatisticsResponse,
    SystemVersionResponse,
)

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_system_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/system/health",
        tags=["System"],
        summary="Health",
        description="Liveness and overall health.",
        response_model=SuccessEnvelope[SystemHealthResponse],
        responses={200: _shared._HEALTH_200, **_shared._standard_errors()},
    )
    def system_health() -> SuccessEnvelope[object]:
        storage_target, read_only = ctx.api.storage_info()
        return ctx.ok(
            SystemHealthResponse(
                status=ctx.api.health(),
                storage_target=storage_target,
                read_only=read_only,
                dev_auth_bypass=ctx.api.dev_auth_bypass(),
            )
        )

    @router.get(
        "/api/v1/system/ready",
        tags=["System"],
        summary="Ready",
        description="Readiness probe.",
        response_model=SuccessEnvelope[SystemHealthResponse],
        responses={200: _shared._READY_200, **_shared._standard_errors()},
    )
    def system_ready() -> SuccessEnvelope[object]:
        return ctx.ok(SystemHealthResponse(status="ready"))

    @router.get(
        "/api/v1/system/live",
        tags=["System"],
        summary="Live",
        description="Liveness probe.",
        response_model=SuccessEnvelope[SystemHealthResponse],
        responses={200: _shared._LIVE_200, **_shared._standard_errors()},
    )
    def system_live() -> SuccessEnvelope[object]:
        return ctx.ok(SystemHealthResponse(status="live"))

    @router.get(
        "/api/v1/system/version",
        tags=["System"],
        summary="Version",
        description="OSAP API version.",
        response_model=SuccessEnvelope[SystemVersionResponse],
        responses={200: _shared._VERSION_200, **_shared._standard_errors()},
    )
    def system_version() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.version())

    @router.get(
        "/api/v1/system/statistics",
        tags=["System"],
        summary="Statistics",
        description="System statistics.",
        response_model=SuccessEnvelope[SystemStatisticsResponse],
        responses={200: _shared._STATISTICS_200, **_shared._standard_errors()},
    )
    def system_statistics() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.statistics())

    return router
