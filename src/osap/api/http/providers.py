"""Router de providers: list/get/status (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Response

from src.osap.api.contracts import ErrorEnvelope, ProviderResponse, SuccessEnvelope

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_providers_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/providers",
        tags=["Providers"],
        summary="List providers",
        description="Lists provider state and capabilities.",
        response_model=SuccessEnvelope[list[ProviderResponse]],
        responses={200: _shared._PROVIDER_LIST_200, **_shared._standard_errors()},
    )
    def list_providers() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.list_providers())

    @router.get(
        "/api/v1/providers/{provider_id}",
        tags=["Providers"],
        summary="Get a provider",
        description="Retrieves a single provider.",
        response_model=SuccessEnvelope[ProviderResponse] | ErrorEnvelope,
        responses={200: _shared._PROVIDER_GET_200, **_shared._standard_errors(404)},
    )
    def get_provider(provider_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        provider = ctx.api.get_provider(provider_id)
        if provider is None:
            return ctx.fail(404, response, "NOT_FOUND", "Provider not found")
        return ctx.ok(provider)

    @router.get(
        "/api/v1/providers/{provider_id}/status",
        tags=["Providers"],
        summary="Provider status",
        description="Retrieves provider status.",
        response_model=SuccessEnvelope[ProviderResponse] | ErrorEnvelope,
        responses={200: _shared._PROVIDER_GET_200, **_shared._standard_errors(404)},
    )
    def provider_status(provider_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        provider = ctx.api.get_provider(provider_id)
        if provider is None:
            return ctx.fail(404, response, "NOT_FOUND", "Provider not found")
        return ctx.ok(provider)

    return router
