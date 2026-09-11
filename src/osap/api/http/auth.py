"""Router de auth: registro, verificación, dev-session y OIDC (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from src.osap.api.contracts import (
    ErrorEnvelope,
    RegisterRequest,
    SuccessEnvelope,
    VerifyEmailRequest,
)
from src.osap.domain.votes import ForbiddenError
from src.osap.infrastructure.auth.auth_proxy_client import AuthProxyError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_auth_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.post(
        "/api/v1/auth/register",
        status_code=200,
        tags=["Auth"],
        summary="Register user",
        description="Registra un usuario vía osap-auth (proxy público, sin service client). "
        "Anti-enumeración: email ya existente devuelve la misma respuesta genérica.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Register result", _shared._example({})),
            422: _shared._INVALID_VOTE_422,
            429: _shared._resp("Rate limited", _shared._error("RATE_LIMITED", "Too many requests")),
            502: _shared._resp("Bad gateway", _shared._error("BAD_GATEWAY", "Identity service unreachable")),
            **_shared._standard_errors(),
        },
    )
    def register_user(
        payload: RegisterRequest,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            status, doc = ctx.api.register_user(payload.email, payload.password, payload.name)
        except AuthProxyError:
            return ctx.fail(502, response, "BAD_GATEWAY", "Identity service unreachable")
        if status == 422:
            return ctx.fail(422, response, "VALIDATION_ERROR", "Invalid email/password/name")
        if status == 429:
            return ctx.fail(429, response, "RATE_LIMITED", "Too many requests")
        if status >= 500:
            return ctx.fail(502, response, "BAD_GATEWAY", "Identity service unavailable")
        return ctx.ok(doc)

    @router.post(
        "/api/v1/auth/dev-session",
        tags=["Auth"],
        summary="Dev admin session (SOLO desarrollo)",
        description="Devuelve una sesión admin de desarrollo. Solo activa con "
        "OSAP_DEV_AUTH_BYPASS=1; NUNCA en producción.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={200: _shared._resp("Session", _shared._example({})), 403: _shared._FORBIDDEN_403},
    )
    def dev_session(response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.dev_session())
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Dev auth bypass not enabled")

    @router.get(
        "/api/v1/auth/oidc/start",
        tags=["Auth"],
        summary="Start OIDC login (authorize URL)",
        description="Genera el estado PKCE y devuelve la URL de authorize de osap-auth para "
        "redirigir el navegador (login vía IdP).",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("OIDC start", _shared._example({})),
            503: _shared._resp("Not configured", _shared._example({})),
        },
    )
    def oidc_start(response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.oidc_start())
        except Exception as exc:  # noqa: BLE001
            return ctx.fail(503, response, "OIDC_NOT_CONFIGURED", str(exc))

    @router.get(
        "/api/v1/auth/oidc/callback",
        include_in_schema=False,
        response_model=None,
    )
    def oidc_callback(
        code: str | None, state: str | None, response: Response
    ) -> RedirectResponse | HTMLResponse:
        try:
            redirect_url = ctx.api.oidc_callback(code, state)
        except Exception as exc:  # noqa: BLE001
            # Siempre redirigir a la SPA (con error) para que el popup cierre y el error
            # llegue a la ventana principal.
            redirect_url = ctx.api.oidc_error_url(f"Error en el intercambio de tokens OIDC: {exc}")
        return RedirectResponse(redirect_url, status_code=302)

    @router.post(
        "/api/v1/auth/verify-email",
        status_code=200,
        tags=["Auth"],
        summary="Verify email",
        description="Verifica el email de un usuario vía osap-auth (proxy público).",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Email verified", _shared._example({})),
            422: _shared._INVALID_VOTE_422,
            502: _shared._resp("Bad gateway", _shared._error("BAD_GATEWAY", "Identity service unreachable")),
            **_shared._standard_errors(),
        },
    )
    def verify_email(payload: VerifyEmailRequest, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            status, doc = ctx.api.verify_email(payload.token)
        except AuthProxyError:
            return ctx.fail(502, response, "BAD_GATEWAY", "Identity service unreachable")
        if status == 422:
            return ctx.fail(422, response, "VALIDATION_ERROR", "Invalid token")
        if status >= 500:
            return ctx.fail(502, response, "BAD_GATEWAY", "Identity service unavailable")
        return ctx.ok(doc)

    return router
