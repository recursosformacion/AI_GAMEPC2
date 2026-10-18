"""Router de notificaciones (campana de la app)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Response

from src.osap.api.contracts import ErrorEnvelope, SuccessEnvelope

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_notifications_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/notifications",
        tags=["Notifications"],
        summary="Mis notificaciones",
        description="Bandeja del usuario (y avisos globales si es admin). Requiere login.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Notifications", _shared._example({"items": [], "unread": 0})),
            401: _shared._UNAUTHORIZED_401,
        },
    )
    def list_notifications(
        response: Response,
        limit: int = 50,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        data = ctx.api.list_notifications(authorization, limit)
        if data is None:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        return ctx.ok(data)

    @router.get(
        "/api/v1/notifications/count",
        tags=["Notifications"],
        summary="No leídas",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Unread count", _shared._example({"unread": 0})),
            401: _shared._UNAUTHORIZED_401,
        },
    )
    def count_unread(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        count = ctx.api.count_unread_notifications(authorization)
        if count is None:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        return ctx.ok({"unread": count})

    @router.post(
        "/api/v1/notifications/{notification_id}/read",
        tags=["Notifications"],
        summary="Marcar una notificación como leída",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Read", _shared._example({"ok": True})),
            401: _shared._UNAUTHORIZED_401,
        },
    )
    def mark_read(
        notification_id: int,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        ok = ctx.api.mark_notification_read(authorization, notification_id)
        if ok is None:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        return ctx.ok({"ok": ok})

    @router.post(
        "/api/v1/notifications/read-all",
        tags=["Notifications"],
        summary="Marcar todas como leídas",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Read all", _shared._example({"ok": True})),
            401: _shared._UNAUTHORIZED_401,
        },
    )
    def mark_all(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        ok = ctx.api.mark_all_notifications_read(authorization)
        if ok is None:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        return ctx.ok({"ok": ok})

    return router
