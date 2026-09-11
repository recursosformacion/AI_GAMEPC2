"""Router de admin: overview y mantenimiento (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Header, Response

from src.osap.api.contracts import (
    AdminOverviewResponse,
    ErrorEnvelope,
    SuccessEnvelope,
)
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_admin_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/admin/overview",
        tags=["Composers"],
        summary="Admin overview (composer review stats + source suggestions)",
        description="Resumen de administración: conteo de compositores por estado de revisión "
        "y número de sugerencias de fuente pendientes. Exige role=admin.",
        response_model=SuccessEnvelope[AdminOverviewResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Overview", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def admin_overview(
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            overview = ctx.api.admin_overview(authorization)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        return ctx.ok(
            AdminOverviewResponse(
                composers=cast("dict[str, int]", overview["composers"]),
                source_suggestions_pending=cast("int", overview["source_suggestions_pending"]),
                source_suggestions=cast("dict[str, int]", overview["source_suggestions"]),
                storage=cast("dict[str, int]", overview.get("storage", {})),
            )
        )

    return router
