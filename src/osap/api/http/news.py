"""Router de noticias musicales (sesión OSAP → ai_noticias)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Query, Response

from src.osap.api.contracts import ErrorEnvelope, SuccessEnvelope
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError
from src.osap.infrastructure.news.client import NewsUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.osap.api.http.context import HttpContext


def _call(
    ctx: HttpContext, response: Response, fn: Callable[[], object]
) -> SuccessEnvelope[object] | ErrorEnvelope:
    try:
        return ctx.ok(fn())
    except UnauthenticatedError:
        return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
    except ForbiddenError as exc:
        return ctx.fail(403, response, "FORBIDDEN", str(exc) or "Forbidden")
    except NewsUnavailableError:
        return ctx.fail(
            503, response, "NEWS_UNAVAILABLE", "El servicio de noticias no está disponible"
        )


def build_news_router(ctx: HttpContext) -> APIRouter:
    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/news/topics",
        tags=["News"],
        summary="Temas de noticias disponibles",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: {"description": "Login required"}, 503: {"description": "News unavailable"}},
    )
    def news_topics(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        return _call(ctx, response, lambda: ctx.api.news_topics(authorization))

    @router.get(
        "/api/v1/news",
        tags=["News"],
        summary="Noticias para el usuario autenticado",
        description=(
            "Usa el idioma y los temas de la cuenta OSAP. La lectura en la web no envía "
            "correos; el consentimiento de comunicaciones es independiente."
        ),
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={401: {"description": "Login required"}, 503: {"description": "News unavailable"}},
    )
    def news(
        response: Response,
        topics: str | None = Query(None, description="Filtro temporal separado por comas"),
        language: str | None = Query(None),
        languages: str | None = Query(None, description="Idiomas separados por comas"),
        limit: int = Query(20, ge=1, le=100),
        days: int = Query(30, ge=1, le=3650),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        selected = (
            [part.strip() for part in topics.split(",") if part.strip()]
            if topics is not None
            else None
        )
        selected_languages = (
            [part.strip() for part in languages.split(",") if part.strip()]
            if languages is not None
            else ([language] if language else None)
        )
        return _call(
            ctx,
            response,
            lambda: ctx.api.news_feed(
                authorization,
                limit=limit,
                days=days,
                topics=selected,
                languages=selected_languages,
            ),
        )

    return router

