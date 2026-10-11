"""Router de «Los amigos»: grupos, artículos, recursos y moderación editorial.

- Público: consulta de grupos y artículos PUBLICADOS (sin login).
- Autenticado: creación/edición de artículos por miembros activos del grupo.
- Admin de grupo / admin global: grupos, membresías, aprobación y auditoría.

La autorización se aplica SIEMPRE en el servidor (membresías del grupo), no en el frontend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Query, Response

from src.osap.api.contracts import (
    AmigosArticleCreateRequest,
    AmigosArticleUpdateRequest,
    AmigosCoralDetailsUpdate,
    AmigosGroupCreateRequest,
    AmigosGroupUpdateRequest,
    AmigosMemberGrantRequest,
    ErrorEnvelope,
    SuccessEnvelope,
)
from src.osap.api.http.context import HttpContext, standard_errors
from src.osap.application.amigos import AmigosError
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

if TYPE_CHECKING:
    from collections.abc import Callable


def _call(
    ctx: HttpContext, response: Response, fn: Callable[[], object]
) -> SuccessEnvelope[object] | ErrorEnvelope:
    try:
        return ctx.ok(fn())
    except UnauthenticatedError:
        return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
    except ForbiddenError as exc:
        return ctx.fail(403, response, "FORBIDDEN", str(exc) or "Forbidden")
    except AmigosError as exc:
        return ctx.fail(exc.status, response, exc.code, exc.message)


def build_amigos_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    # --- lectura pública -----------------------------------------------------

    @router.get(
        "/api/v1/amigos/groups",
        tags=["Friends"],
        summary="Grupos de «Los amigos» (público)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={200: _shared._resp("Groups", _shared._example([]))},
    )
    def list_groups(
        response: Response,
        kind: str | None = Query(None),
        include_inactive: bool = Query(False),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_list_groups(
                token=authorization, include_inactive=include_inactive, kind=kind
            ),
        )

    @router.get(
        "/api/v1/amigos/groups/{group_id}/articles",
        tags=["Friends"],
        summary="Artículos publicados de un grupo (público)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses=standard_errors(404),
    )
    def group_articles(
        group_id: str,
        response: Response,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        if not ctx.api.amigos_group_exists(group_id):
            return ctx.fail(404, response, "GROUP_NOT_FOUND", "Grupo no encontrado")
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_group_articles(group_id, limit=limit, offset=offset),
        )

    @router.get(
        "/api/v1/amigos/groups/{group_id}/coral",
        tags=["Friends"],
        summary="Ficha estructurada de un coral (público)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses=standard_errors(404),
    )
    def coral_details(group_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        if not ctx.api.amigos_group_exists(group_id):
            return ctx.fail(404, response, "GROUP_NOT_FOUND", "Grupo no encontrado")

        def run() -> object:
            data = ctx.api.amigos_coral_details(group_id)
            if data is None:
                raise AmigosError(404, "CORAL_NOT_FOUND", "El grupo no es de tipo coral")
            return data

        return _call(ctx, response, run)

    @router.get(
        "/api/v1/amigos/articles/{article_id}",
        tags=["Friends"],
        summary="Artículo (público si está publicado; autor/admin si no)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses=standard_errors(404),
    )
    def get_article(
        article_id: str,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        def run() -> object:
            article = ctx.api.amigos_article(article_id, token=authorization)
            if article is None:
                raise AmigosError(404, "ARTICLE_NOT_FOUND", "Artículo no encontrado")
            return article

        return _call(ctx, response, run)

    # --- usuario autenticado -------------------------------------------------

    @router.get(
        "/api/v1/amigos/my",
        tags=["Friends"],
        summary="Mis artículos",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401},
    )
    def my_articles(
        response: Response,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_my_articles(authorization, limit=limit, offset=offset),
        )

    @router.get(
        "/api/v1/amigos/my/groups",
        tags=["Friends"],
        summary="Grupos en los que puedo colaborar (con mi rol)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401},
    )
    def my_groups(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_my_groups(authorization))

    @router.post(
        "/api/v1/amigos/groups/{group_id}/articles",
        tags=["Friends"],
        summary="Crear un artículo (borrador o publicar)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 409, 422)},
    )
    def create_article(
        group_id: str,
        payload: AmigosArticleCreateRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_create_article(authorization, group_id, payload),
        )

    @router.patch(
        "/api/v1/amigos/articles/{article_id}",
        tags=["Friends"],
        summary="Editar un artículo",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 409, 422)},
    )
    def update_article(
        article_id: str,
        payload: AmigosArticleUpdateRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        def run() -> object:
            updated = ctx.api.amigos_update_article(authorization, article_id, payload)
            if updated is None:
                raise AmigosError(404, "ARTICLE_NOT_FOUND", "Artículo no encontrado")
            return updated

        return _call(ctx, response, run)

    @router.post(
        "/api/v1/amigos/articles/{article_id}/submit",
        tags=["Friends"],
        summary="Enviar un borrador (pending o publicado según la modalidad del grupo)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 409)},
    )
    def submit_article(
        article_id: str, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_submit_article(authorization, article_id))

    @router.post(
        "/api/v1/amigos/articles/{article_id}/publish",
        tags=["Friends"],
        summary="Publicar un artículo",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 409)},
    )
    def publish_article(
        article_id: str, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_publish_article(authorization, article_id))

    @router.post(
        "/api/v1/amigos/articles/{article_id}/withdraw",
        tags=["Friends"],
        summary="Retirar un artículo (no se borra)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 409)},
    )
    def withdraw_article(
        article_id: str, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_withdraw_article(authorization, article_id))

    # --- administración de grupos -------------------------------------------

    @router.post(
        "/api/v1/admin/amigos/groups",
        tags=["Friends"],
        summary="Crear un grupo (solo admin global)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 409, 422)},
    )
    def create_group(
        payload: AmigosGroupCreateRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_create_group(authorization, payload))

    @router.patch(
        "/api/v1/admin/amigos/groups/{group_id}",
        tags=["Friends"],
        summary="Editar un grupo (admin del grupo o admin global)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 422)},
    )
    def update_group(
        group_id: str,
        payload: AmigosGroupUpdateRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        def run() -> object:
            updated = ctx.api.amigos_update_group(authorization, group_id, payload)
            if updated is None:
                raise AmigosError(404, "GROUP_NOT_FOUND", "Grupo no encontrado")
            return updated

        return _call(ctx, response, run)

    @router.put(
        "/api/v1/admin/amigos/groups/{group_id}/coral",
        tags=["Friends"],
        summary="Editar la ficha estructurada de un coral (admin del grupo)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 422)},
    )
    def update_coral_details(
        group_id: str,
        payload: AmigosCoralDetailsUpdate,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_update_coral_details(authorization, group_id, payload),
        )

    # --- membresías ----------------------------------------------------------

    @router.get(
        "/api/v1/admin/amigos/groups/{group_id}/members",
        tags=["Friends"],
        summary="Miembros de un grupo (admin del grupo o global)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404)},
    )
    def list_members(
        group_id: str, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_list_members(authorization, group_id))

    @router.post(
        "/api/v1/admin/amigos/groups/{group_id}/members",
        tags=["Friends"],
        summary="Autorizar a un usuario en el grupo",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 422)},
    )
    def grant_member(
        group_id: str,
        payload: AmigosMemberGrantRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_grant_member(authorization, group_id, payload),
        )

    @router.delete(
        "/api/v1/admin/amigos/groups/{group_id}/members/{user_id}",
        tags=["Friends"],
        summary="Revocar la membresía de un usuario (no borra sus artículos)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404)},
    )
    def revoke_member(
        group_id: str,
        user_id: str,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_revoke_member(authorization, group_id, user_id),
        )

    # --- moderación editorial ------------------------------------------------

    @router.get(
        "/api/v1/admin/amigos/groups/{group_id}/articles",
        tags=["Friends"],
        summary="Todos los artículos del grupo (incluye no publicados) para su gestión",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404)},
    )
    def manage_articles(
        group_id: str,
        response: Response,
        limit: int = Query(200, ge=1, le=500),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_group_articles(
                group_id, token=authorization, include_non_public=True, limit=limit, offset=offset
            ),
        )

    @router.get(
        "/api/v1/admin/amigos/pending",
        tags=["Friends"],
        summary="Artículos pendientes de aprobación (de mis grupos o todos si admin global)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401},
    )
    def pending_articles(
        response: Response,
        group_id: str | None = Query(default=None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_pending(authorization, group_id, limit=limit, offset=offset),
        )

    @router.post(
        "/api/v1/admin/amigos/articles/{article_id}/approve",
        tags=["Friends"],
        summary="Aprobar y publicar un artículo pendiente",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 409)},
    )
    def approve_article(
        article_id: str, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_approve_article(authorization, article_id))

    @router.post(
        "/api/v1/admin/amigos/articles/{article_id}/return",
        tags=["Friends"],
        summary="Devolver un artículo pendiente al autor para corrección",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404, 409)},
    )
    def return_article(
        article_id: str,
        response: Response,
        note: str = Query(""),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(
            ctx, response,
            lambda: ctx.api.amigos_return_article(authorization, article_id, note),
        )

    @router.get(
        "/api/v1/admin/amigos/groups/{group_id}/audit",
        tags=["Friends"],
        summary="Historial de acciones del grupo (auditoría)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: _shared._UNAUTHORIZED_401, **_shared._standard_errors(403, 404)},
    )
    def group_audit(
        group_id: str, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.amigos_audit(authorization, group_id))

    return router
