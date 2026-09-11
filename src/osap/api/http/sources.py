"""Router de sources: catálogo de repositorios, fuentes de sesión y sugerencias (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, Response

from src.osap.api.contracts import (
    DiscoverSource,
    ErrorEnvelope,
    RepositorySource,
    RepositorySourceSummary,
    SessionSource,
    SessionSourceCreate,
    SourcePreviewRequest,
    SourcePreviewResponse,
    SourceSuggestionRead,
    SourceSuggestionRequest,
    SuccessEnvelope,
)
from src.osap.domain.votes import UnauthenticatedError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext

def build_sources_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    # --- repository sources (Source Catalog) ---------------------------------

    @router.get(
        "/api/v1/repository-sources",
        tags=["Sources"],
        summary="List repository sources",
        description="Lists the permanent source catalog.",
        response_model=SuccessEnvelope[list[RepositorySourceSummary]],
        responses={200: _shared._SOURCES_LIST_200, **_shared._standard_errors()},
    )
    def list_repository_sources() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.list_repository_sources())

    @router.get(
        "/api/v1/repository-sources/{source_id}",
        tags=["Sources"],
        summary="Get a repository source",
        description="Retrieves the full catalog ficha of a repository source.",
        response_model=SuccessEnvelope[RepositorySource] | ErrorEnvelope,
        responses={200: _shared._SOURCE_GET_200, **_shared._standard_errors(404)},
    )
    def get_repository_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = ctx.api.get_repository_source(source_id)
        if source is None:
            return ctx.fail(404, response, "NOT_FOUND", "Repository source not found")
        return ctx.ok(source)

    # --- session sources (user's temporary sources) -------------------------

    @router.post(
        "/api/v1/sources",
        status_code=201,
        tags=["Sources"],
        summary="Add a source",
        description="Creates a temporary (Session) source for the current search/session.",
        response_model=SuccessEnvelope[SessionSource],
        responses={
            201: _shared._resp(
                "Source created",
                _shared._example(
                    {
                        "source_id": "src-1",
                        "name": "My folder",
                        "type": "Local",
                        "location": "/path",
                        "status": "CREATED",
                        "created_at": "...",
                    }
                ),
            )
        },
    )
    def create_source(payload: SessionSourceCreate) -> SuccessEnvelope[object]:
        source = ctx.api.create_session_source(payload.name, payload.type, payload.location)
        return ctx.ok(source)

    @router.get(
        "/api/v1/sources",
        tags=["Sources"],
        summary="List session sources",
        description="Lists the user's temporary sources.",
        response_model=SuccessEnvelope[list[SessionSource]],
        responses={200: _shared._resp("Session sources", _shared._example([]))},
    )
    def list_sources() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.list_session_sources())

    @router.get(
        "/api/v1/sources/{source_id}",
        tags=["Sources"],
        summary="Get a session source",
        description="Retrieves a user's temporary source.",
        response_model=SuccessEnvelope[SessionSource] | ErrorEnvelope,
        responses={200: _shared._resp("Session source", _shared._example({})), **_shared._standard_errors(404)},
    )
    def get_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = ctx.api.get_session_source(source_id)
        if source is None:
            return ctx.fail(404, response, "NOT_FOUND", "Session source not found")
        return ctx.ok(source)

    @router.delete(
        "/api/v1/sources/{source_id}",
        tags=["Sources"],
        summary="Forget a session source",
        description="Removes a user's temporary source.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={200: _shared._resp("Forget", _shared._example(True)), **_shared._standard_errors(404)},
    )
    def forget_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        if not ctx.api.forget_session_source(source_id):
            return ctx.fail(404, response, "NOT_FOUND", "Session source not found")
        return ctx.ok(True)

    @router.post(
        "/api/v1/sources/{source_id}/analyze",
        tags=["Sources"],
        summary="Analyze a session source",
        description="Runs automatic analysis on a temporary source.",
        response_model=SuccessEnvelope[SessionSource] | ErrorEnvelope,
        responses={200: _shared._resp("Analyzed", _shared._example({})), **_shared._standard_errors(404)},
    )
    def analyze_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = ctx.api.analyze_session_source(source_id)
        if source is None:
            return ctx.fail(404, response, "NOT_FOUND", "Session source not found")
        return ctx.ok(source)

    @router.post(
        "/api/v1/sources/{source_id}/use",
        tags=["Sources"],
        summary="Use a session source",
        description="Uses a temporary source in the current search/session.",
        response_model=SuccessEnvelope[SessionSource] | ErrorEnvelope,
        responses={200: _shared._resp("Used", _shared._example({})), **_shared._standard_errors(404)},
    )
    def use_source(source_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = ctx.api.use_session_source(source_id)
        if source is None:
            return ctx.fail(404, response, "NOT_FOUND", "Session source not found")
        return ctx.ok(source)

    @router.post(
        "/api/v1/sources/preview",
        tags=["Sources"],
        summary="Preview a source (check JSON / infer mapping)",
        description="Reads the source URL, validates its JSON and infers the field mapping.",
        response_model=SuccessEnvelope[SourcePreviewResponse] | ErrorEnvelope,
        responses={200: _shared._resp("Preview", _shared._example({})), **_shared._standard_errors(422)},
    )
    def preview_source(payload: SourcePreviewRequest) -> SuccessEnvelope[object]:
        ok_flag, fields, error = ctx.api.preview_source(payload.url)
        return ctx.ok(SourcePreviewResponse(ok=ok_flag, fields=fields, error=error))

    @router.post(
        "/api/v1/sources/suggest",
        tags=["Sources"],
        summary="Suggest a source to the administrator",
        description="Requires login. Adds the source to the session and creates a "
        "suggestion pending admin approval.",
        response_model=SuccessEnvelope[SourceSuggestionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Suggested", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def suggest_source(
        payload: SourceSuggestionRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            suggestion = ctx.api.suggest_source(
                authorization, payload.name, payload.type, payload.location, payload.mapping
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required to suggest a source")
        return ctx.ok(suggestion)

    @router.get(
        "/api/v1/discover/sources",
        tags=["Sources"],
        summary="Discover sources",
        description="Suggestions of new sources (discovery catalog).",
        response_model=SuccessEnvelope[list[DiscoverSource]],
        responses={200: _shared._resp("Discover", _shared._example([]))},
    )
    def discover_sources() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.discover_sources())

    return router
