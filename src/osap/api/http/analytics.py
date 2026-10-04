"""Router de analítica de uso (admin).

Expone los agregados diarios de uso (búsquedas y descargas). Separado de `work_statistics`
(valoración por votos, en osap-storage). Diseño: `docs/osap/usage-analytics-design.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Query, Response

from src.osap.api.contracts import (
    ActivityMeResponse,
    AnalyticsMeResponse,
    AnalyticsOverviewResponse,
    ErrorEnvelope,
    FunnelMetricsResponse,
    SuccessEnvelope,
)
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError
from src.osap.infrastructure.state.analytics.memory import today

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_analytics_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/admin/analytics/overview",
        tags=["Admin"],
        summary="Analytics overview (usage)",
        description="Agregados diarios de uso (búsquedas con/sin resultados y descargas) en "
        "el rango [from_day, to_day] (YYYY-MM-DD; por defecto, hoy). Exige role=admin.",
        response_model=SuccessEnvelope[AnalyticsOverviewResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Analytics overview", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def analytics_overview(
        response: Response,
        from_day: str | None = Query(default=None),
        to_day: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            ctx.api.require_admin(authorization)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        default_day = today()
        start = from_day or default_day
        end = to_day or default_day
        if start > end:
            start, end = end, start
        data = ctx.api.analytics_overview(start, end)
        return ctx.ok(AnalyticsOverviewResponse(from_day=start, to_day=end, **data))

    @router.get(
        "/api/v1/analytics/me",
        tags=["Quota"],
        summary="My usage analytics",
        description="Estadísticas del propio usuario autenticado (descargas, cuota y etapa del "
        "funnel). La identidad se toma del token; no acepta parámetros de usuario.",
        response_model=SuccessEnvelope[AnalyticsMeResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("My analytics", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
        },
    )
    def analytics_me(
        response: Response,
        from_day: str | None = Query(default=None),
        to_day: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        data = ctx.api.analytics_me(authorization, from_day, to_day)
        if data is None:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        return ctx.ok(AnalyticsMeResponse.model_validate(data))

    @router.get(
        "/api/v1/activity/me",
        tags=["Quota"],
        summary="Mi Actividad (panel personal)",
        description="Panel de actividad del usuario autenticado: resumen (descargas/cuota), "
        "aportaciones, pendientes, mis descargas, impacto y actividad reciente. Identidad del token.",
        response_model=SuccessEnvelope[ActivityMeResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Mi Actividad", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
        },
    )
    def activity_me(
        response: Response,
        from_day: str | None = Query(default=None),
        to_day: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        data = ctx.api.activity_me(authorization, from_day, to_day)
        if data is None:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        return ctx.ok(ActivityMeResponse.model_validate(data))

    @router.get(
        "/api/v1/admin/analytics/funnel",
        tags=["Admin"],
        summary="Funnel metrics (S0-S4)",
        description="Métricas del funnel de acceso/contribución (eventos y usuarios únicos) "
        "derivadas de `funnel_events` + `download_usage` en [from_day, to_day]. Exige role=admin.",
        response_model=SuccessEnvelope[FunnelMetricsResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Funnel metrics", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def admin_funnel_metrics(
        response: Response,
        from_day: str | None = Query(default=None),
        to_day: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            ctx.api.require_admin(authorization)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        default_day = today()
        start = from_day or default_day
        end = to_day or default_day
        if start > end:
            start, end = end, start
        return ctx.ok(FunnelMetricsResponse.model_validate(ctx.api.funnel_metrics(start, end)))

    return router
