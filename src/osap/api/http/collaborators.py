"""Router público de colaboradores (fachada osap-api).

`GET /api/v1/public/collaborators?project=…`: `osap-support` aporta por M2M los
reconocimientos ACTIVOS del proyecto y `osap-auth` el consentimiento de cuenta + nickname. Se
publica solo con `nickname_public_consent = true`, mostrando el **nickname**. **Nunca** se
expone el `user_id`, email, `name`, economía ni metadatos internos. Sin migración: composición.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from src.osap.api.contracts import ErrorEnvelope, SuccessEnvelope
from src.osap.api.http.context import HttpContext, standard_errors
from src.osap.application.collaborators import (
    CollaboratorsUnavailableError,
    PublicProjectNotFoundError,
)


def build_collaborators_router(ctx: HttpContext) -> APIRouter:
    router = APIRouter(prefix="/api/v1/public", tags=["Collaborators"])

    @router.get(
        "/collaborators",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses=standard_errors(404, 502),
    )
    def collaborators(
        response: Response,
        project: str = Query("omr", min_length=1),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            data = ctx.container.collaborators().execute(project)
        except PublicProjectNotFoundError as exc:
            return ctx.fail(404, response, "PROJECT_NOT_FOUND", str(exc))
        except CollaboratorsUnavailableError as exc:
            return ctx.fail(502, response, "UPSTREAM_UNAVAILABLE", str(exc))
        return ctx.ok(data)

    return router
