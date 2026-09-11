"""Router de support: contacto y correcciones de catálogo (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Response

from src.osap.api.contracts import (
    CorrectionRead,
    CorrectionRequest,
    CorrectionResolveRequest,
    ErrorEnvelope,
    SuccessEnvelope,
)
from src.osap.application.corrections import CorrectionError
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_support_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    # --- support: contacto y correcciones de catálogo -------------------------

    @router.post(
        "/api/v1/contact",
        tags=["Support"],
        summary="Contacto general (público)",
        description="Registra una solicitud de contacto (sin login). Queda `pending`.",
        response_model=SuccessEnvelope[CorrectionRead] | ErrorEnvelope,
        responses={200: _shared._resp("Contact", _shared._example({})), **_shared._standard_errors(422)},
    )
    def contact_general(
        payload: CorrectionRequest,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            correction = ctx.api.submit_correction(
                None, "contact", payload.message, contact_email=payload.contact_email
            )
        except CorrectionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        return ctx.ok(correction)

    @router.post(
        "/api/v1/corrections",
        tags=["Support"],
        summary="Proponer corrección de datos del catálogo",
        description=(
            "Requiere login. kind: source | composer | work. La corrección se describe "
            "en `message` (texto libre); entity_id identifica la entidad. field / "
            "current_value / proposed_value son metadatos opcionales. Para obras solo se "
            "revisa el título (backend fija entity_provider=omr). No modifica el catálogo: "
            "queda `pending` de revisión."
        ),
        response_model=SuccessEnvelope[CorrectionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Correction", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            **_shared._standard_errors(404, 422),
        },
    )
    def propose_correction(
        payload: CorrectionRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            correction = ctx.api.submit_correction(
                authorization,
                payload.kind,
                payload.message,
                entity_id=payload.entity_id,
                entity_provider=payload.entity_provider,
                field=payload.field,
                current_value=payload.current_value,
                proposed_value=payload.proposed_value,
                contact_email=payload.contact_email,
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required to submit a correction")
        except CorrectionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        return ctx.ok(correction)

    @router.get(
        "/api/v1/admin/corrections",
        tags=["Support"],
        summary="List correction requests (admin)",
        description="Lista las solicitudes de contacto/corrección (admin).",
        response_model=SuccessEnvelope[list[CorrectionRead]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Corrections", _shared._example([])),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def list_corrections_admin(
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.list_corrections(authorization))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.post(
        "/api/v1/admin/corrections/{correction_id}/resolve",
        tags=["Support"],
        summary="Resolve a correction request (admin)",
        description="action: review | close. Solo cambia el estado; NO aplica la corrección.",
        response_model=SuccessEnvelope[CorrectionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Correction", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def resolve_correction_admin(
        correction_id: str,
        payload: CorrectionResolveRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            resolved = ctx.api.resolve_correction(
                authorization, correction_id, payload.action, payload.message
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        if resolved is None:
            return ctx.fail(404, response, "NOT_FOUND", "Correction request not found")
        return ctx.ok(resolved)





    return router
