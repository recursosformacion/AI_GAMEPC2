"""Router de aportaciones (contributions): ciclo de vida add_resource (usuario + admin)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Query, Request, Response

from src.osap.api.contracts import (
    ContributionArtifactRequest,
    ContributionCreateRequest,
    ContributionListRead,
    ContributionRead,
    ContributionRelationReviewRequest,
    ContributionReviewRequest,
    ErrorEnvelope,
    SuccessEnvelope,
)
from src.osap.application.contributions import ContributionError
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_contributions_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    # --- usuario -------------------------------------------------------------

    @router.post(
        "/api/v1/contributions",
        tags=["Support"],
        summary="Crear una aportación (add_resource)",
        description=(
            "Requiere login. En este bloque solo `operation=add_resource` con "
            "`target_kind=representation` y `target_id=representation_id`. Queda en `draft`; "
            "no modifica el catálogo."
        ),
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            **_shared._standard_errors(404, 422),
        },
    )
    def create_contribution(
        payload: ContributionCreateRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            created = ctx.api.create_contribution(
                authorization,
                payload.operation,
                payload.target_kind,
                payload.target_id,
                payload.declared_source,
                [r.model_dump() for r in payload.relations],
                payload.payload,
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ContributionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        return ctx.ok(created)

    @router.get(
        "/api/v1/contributions",
        tags=["Support"],
        summary="Mis aportaciones",
        response_model=SuccessEnvelope[ContributionListRead] | ErrorEnvelope,
        responses={200: _shared._resp("Contributions", _shared._example({})), 401: _shared._UNAUTHORIZED_401},
    )
    def list_my_contributions(
        response: Response,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.list_my_contributions(authorization, limit, offset))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")

    @router.get(
        "/api/v1/contributions/{contribution_id}",
        tags=["Support"],
        summary="Consultar una aportación propia",
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            404: _shared._NOT_FOUND_404,
        },
    )
    def get_contribution(
        contribution_id: int,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            found = ctx.api.get_contribution(authorization, contribution_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        if found is None:
            return ctx.fail(404, response, "NOT_FOUND", "Contribution not found")
        return ctx.ok(found)

    @router.post(
        "/api/v1/contributions/{contribution_id}/artifacts",
        tags=["Support"],
        summary="Adjuntar un fichero (artifact) a una aportación",
        description="Asocia un `file_id` ya existente. No sube bytes (el upload de storage es aparte).",
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            **_shared._standard_errors(403, 404, 409, 422),
        },
    )
    def add_artifact(
        contribution_id: int,
        payload: ContributionArtifactRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            updated = ctx.api.add_contribution_artifact(
                authorization, contribution_id, payload.file_id, payload.kind
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ContributionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        return ctx.ok(updated)

    @router.post(
        "/api/v1/contributions/{contribution_id}/upload",
        tags=["Support"],
        summary="Subir un fichero y adjuntarlo a la aportación",
        description=(
            "Recibe el contenido por el body y los metadatos por query (`name`, `mime_type`). "
            "API lo reenvía a storage (`POST /api/v1/files/upload`) y registra el artifact. "
            "El fichero queda **no público**."
        ),
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            **_shared._standard_errors(403, 404, 409, 422, 502),
        },
    )
    async def upload_contribution(
        contribution_id: int,
        request: Request,
        response: Response,
        name: str = Query(..., min_length=1),
        mime_type: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        data = await request.body()
        if not data:
            return ctx.fail(422, response, "EMPTY_UPLOAD", "El contenido está vacío")
        try:
            updated = ctx.api.upload_contribution(authorization, contribution_id, name, mime_type, data)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ContributionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        return ctx.ok(updated)

    @router.post(
        "/api/v1/contributions/{contribution_id}/submit",
        tags=["Support"],
        summary="Enviar la aportación a revisión (draft → submitted)",
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            **_shared._standard_errors(403, 404, 409, 422),
        },
    )
    def submit_contribution(
        contribution_id: int,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            updated = ctx.api.submit_contribution(authorization, contribution_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ContributionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        return ctx.ok(updated)

    @router.post(
        "/api/v1/contributions/{contribution_id}/withdraw",
        tags=["Support"],
        summary="Retirar una aportación (no se elimina)",
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            **_shared._standard_errors(403, 404, 409),
        },
    )
    def withdraw_contribution(
        contribution_id: int,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            updated = ctx.api.withdraw_contribution(authorization, contribution_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ContributionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        return ctx.ok(updated)

    # --- administración ------------------------------------------------------

    @router.get(
        "/api/v1/admin/contributions",
        tags=["Support"],
        summary="Listar aportaciones para revisión (admin)",
        response_model=SuccessEnvelope[ContributionListRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contributions", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def list_contributions_admin(
        response: Response,
        status: str | None = Query(default=None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.list_contributions_admin(authorization, status, limit, offset))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.get(
        "/api/v1/admin/contributions/{contribution_id}",
        tags=["Support"],
        summary="Detalle de una aportación (admin)",
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
        },
    )
    def get_contribution_admin(
        contribution_id: int,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            found = ctx.api.get_contribution_admin(authorization, contribution_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        if found is None:
            return ctx.fail(404, response, "NOT_FOUND", "Contribution not found")
        return ctx.ok(found)

    @router.post(
        "/api/v1/admin/contributions/{contribution_id}/review",
        tags=["Support"],
        summary="Revisar una aportación (admin)",
        description=(
            "action: in_review | accept | reject. Aceptar NO materializa el recurso: solo "
            "registra el estado `accepted` (la materialización es el bloque siguiente)."
        ),
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            **_shared._standard_errors(404, 409, 422),
        },
    )
    def review_contribution(
        contribution_id: int,
        payload: ContributionReviewRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            reviewed = ctx.api.review_contribution(
                authorization, contribution_id, payload.action, payload.message
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except ContributionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        if reviewed is None:
            return ctx.fail(404, response, "NOT_FOUND", "Contribution not found")
        return ctx.ok(reviewed)

    @router.post(
        "/api/v1/admin/contributions/{contribution_id}/relations/{relation_id}/review",
        tags=["Support"],
        summary="Revisar una relación declarada (admin)",
        description="action: accept | reject. Eje independiente del estado de la aportación.",
        response_model=SuccessEnvelope[ContributionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Contribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            **_shared._standard_errors(404, 409, 422),
        },
    )
    def review_contribution_relation(
        contribution_id: int,
        relation_id: int,
        payload: ContributionRelationReviewRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            reviewed = ctx.api.review_contribution_relation(
                authorization, contribution_id, relation_id, payload.action, payload.message
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except ContributionError as exc:
            return ctx.fail(exc.status, response, exc.code, exc.message)
        if reviewed is None:
            return ctx.fail(404, response, "NOT_FOUND", "Relation not found")
        return ctx.ok(reviewed)

    return router
