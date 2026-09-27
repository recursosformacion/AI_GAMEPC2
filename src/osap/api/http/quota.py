"""Router de administración de cuotas de descarga OMR (planes, excepciones y estadísticas)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Query, Response
from pydantic import BaseModel

from src.osap.api.contracts import ErrorEnvelope, SuccessEnvelope
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


class PlanUpdate(BaseModel):
    downloads_per_day: int
    valid_from: str | None = None
    valid_until: str | None = None


class OverrideUpdate(BaseModel):
    downloads_per_day: int
    valid_from: str | None = None
    valid_until: str | None = None
    note: str | None = None


def build_quota_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    def _admin_error(response: Response, exc: Exception) -> ErrorEnvelope:
        if isinstance(exc, UnauthenticatedError):
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.get(
        "/api/v1/admin/quota/plans",
        tags=["Quota"],
        summary="Cuotas por plan",
        response_model=SuccessEnvelope[list[dict[str, object]]] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, 403: _shared._FORBIDDEN_403},
    )
    def quota_plans(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.quota_plans(authorization))
        except (UnauthenticatedError, ForbiddenError) as exc:
            return _admin_error(response, exc)

    @router.put(
        "/api/v1/admin/quota/plans/{name}",
        tags=["Quota"],
        summary="Fijar cuota de un plan",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, 403: _shared._FORBIDDEN_403},
    )
    def quota_set_plan(
        name: str,
        payload: PlanUpdate,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            ctx.api.quota_set_plan(
                authorization,
                name,
                payload.downloads_per_day,
                payload.valid_from,
                payload.valid_until,
            )
            return ctx.ok({"name": name, "downloads_per_day": payload.downloads_per_day})
        except (UnauthenticatedError, ForbiddenError) as exc:
            return _admin_error(response, exc)

    @router.get(
        "/api/v1/admin/quota/overrides",
        tags=["Quota"],
        summary="Excepciones de cuota por usuario",
        response_model=SuccessEnvelope[list[dict[str, object]]] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, 403: _shared._FORBIDDEN_403},
    )
    def quota_overrides(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.quota_overrides(authorization))
        except (UnauthenticatedError, ForbiddenError) as exc:
            return _admin_error(response, exc)

    @router.put(
        "/api/v1/admin/quota/overrides/{user_id}",
        tags=["Quota"],
        summary="Crear/actualizar excepción de cuota (con vigencia)",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, 403: _shared._FORBIDDEN_403},
    )
    def quota_set_override(
        user_id: str,
        payload: OverrideUpdate,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            ctx.api.quota_set_override(
                authorization,
                user_id,
                payload.downloads_per_day,
                payload.valid_from,
                payload.valid_until,
                payload.note,
            )
            return ctx.ok({"user_id": user_id, "downloads_per_day": payload.downloads_per_day})
        except (UnauthenticatedError, ForbiddenError) as exc:
            return _admin_error(response, exc)

    @router.delete(
        "/api/v1/admin/quota/overrides/{user_id}",
        tags=["Quota"],
        summary="Quitar excepción de cuota",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, 403: _shared._FORBIDDEN_403},
    )
    def quota_delete_override(
        user_id: str,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            ctx.api.quota_delete_override(authorization, user_id)
            return ctx.ok({"user_id": user_id, "deleted": True})
        except (UnauthenticatedError, ForbiddenError) as exc:
            return _admin_error(response, exc)

    @router.get(
        "/api/v1/admin/quota/usage",
        tags=["Quota"],
        summary="Estadísticas de descargas facturables (download_usage)",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, 403: _shared._FORBIDDEN_403},
    )
    def quota_usage(
        response: Response,
        from_day: str = Query(alias="from"),
        to_day: str = Query(alias="to"),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.quota_usage(authorization, from_day, to_day))
        except (UnauthenticatedError, ForbiddenError) as exc:
            return _admin_error(response, exc)

    return router
