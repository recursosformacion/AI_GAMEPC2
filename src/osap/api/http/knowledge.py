"""Router de knowledge: observaciones/facts/sugerencias (read-only) (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from src.osap.api.contracts import (
    KnowledgeFactDTO,
    KnowledgeObservationDTO,
    KnowledgeSuggestionDTO,
    SuccessEnvelope,
)

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_knowledge_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/knowledge/observations",
        tags=["Knowledge"],
        summary="Knowledge observations",
        description="Lists knowledge observations (read-only).",
        response_model=SuccessEnvelope[list[KnowledgeObservationDTO]],
        responses={200: _shared._KNOWLEDGE_OBSERVATIONS_200, **_shared._standard_errors()},
    )
    def knowledge_observations() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.knowledge().observations)

    @router.get(
        "/api/v1/knowledge/facts",
        tags=["Knowledge"],
        summary="Knowledge facts",
        description="Lists knowledge facts (read-only).",
        response_model=SuccessEnvelope[list[KnowledgeFactDTO]],
        responses={200: _shared._KNOWLEDGE_FACTS_200, **_shared._standard_errors()},
    )
    def knowledge_facts() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.knowledge().facts)

    @router.get(
        "/api/v1/knowledge/suggestions",
        tags=["Knowledge"],
        summary="Knowledge suggestions",
        description="Lists knowledge suggestions (read-only).",
        response_model=SuccessEnvelope[list[KnowledgeSuggestionDTO]],
        responses={200: _shared._KNOWLEDGE_SUGGESTIONS_200, **_shared._standard_errors()},
    )
    def knowledge_suggestions() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.knowledge().suggestions)

    return router
