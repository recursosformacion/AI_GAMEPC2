"""Router de analítica de uso (admin).

Expone los agregados diarios de uso (búsquedas y descargas). Separado de `work_statistics`
(valoración por votos, en osap-storage). Diseño: `docs/osap/usage-analytics-design.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Query, Response

from src.osap.api.contracts import (
    AnalyticsOverviewResponse,
    ErrorEnvelope,
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

    return router
