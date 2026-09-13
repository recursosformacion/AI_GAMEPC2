"""Router de composers (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Response

from src.osap.api.contracts import (
    CatalogueRead,
    ComposerDetailResponse,
    ComposerListResponse,
    ComposerResolveRequest,
    ComposerResolveResponse,
    ComposerWorksResponse,
    ErrorEnvelope,
    SuccessEnvelope,
)
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_composers_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/composers",
        tags=["Composers"],
        summary="List composers",
        description="Consulta pública de compositores (listado, q, paginado). Backend: osap-storage con storage:read.",
        response_model=SuccessEnvelope[ComposerListResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Composers list", _shared._example({})),
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def list_composers(
        response: Response,
        q: str | None = Query(default=None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        review: str | None = Query(
            default=None,
            pattern=r"^(correct|incorrect|reviewed|not_reviewed)$",
            description="Filtro por estado de revisión.",
        ),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            data = ctx.api.list_composers(q, limit, offset, review)
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Composer service is not configured")
        # Recuento de obras desde el ÍNDICE local (el catálogo realmente consultable);
        # osap-storage puede tener 0 si la obra no está vinculada allí.
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            ids = [str(i.get("id")) for i in items if isinstance(i, dict) and i.get("id")]
            counts = ctx.api.index_works_counts(ids)
            for item in items:
                if isinstance(item, dict) and str(item.get("id") or "") in counts:
                    item["works_count"] = counts[str(item["id"])]
        return ctx.ok(_shared._composer_list_dto(data))

    @router.get(
        "/api/v1/composers/{composer_id}",
        tags=["Composers"],
        summary="Composer detail",
        description="Detalle de un compositor. Backend: osap-storage con storage:read.",
        response_model=SuccessEnvelope[ComposerDetailResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Composer detail", _shared._example({})),
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(),
        },
    )
    def get_composer(composer_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            detail = ctx.api.get_composer(composer_id)
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Composer service is not configured")
        # La consulta pública solo expone compositores visibles del Maestro.
        if detail is None or not bool(detail.get("visible", True)):
            return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
        counts = ctx.api.index_works_counts([str(detail.get("id") or "")])
        if str(detail.get("id") or "") in counts:
            detail["works_count"] = counts[str(detail["id"])]
        return ctx.ok(_shared._composer_detail_dto(detail))

    @router.get(
        "/api/v1/composers/{composer_id}/biography",
        tags=["Composers"],
        summary="Composer biography",
        description="Detalle de un compositor con su biografía (resumen, época, nacionalidad, "
        "obras clave, dato clave, referencias) y las obras del compositor. "
        "Backend: osap-storage con storage:read.",
        response_model=SuccessEnvelope[ComposerDetailResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Composer biography", _shared._example({})),
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(),
        },
    )
    def get_composer_biography(composer_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            detail = ctx.api.get_composer_biography(composer_id)
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Composer service is not configured")
        if detail is None or not bool(detail.get("visible", True)):
            return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
        counts = ctx.api.index_works_counts([str(detail.get("id") or "")])
        if str(detail.get("id") or "") in counts:
            detail["works_count"] = counts[str(detail["id"])]
        return ctx.ok(_shared._composer_detail_dto(detail))

    @router.get(
        "/api/v1/catalogues",
        tags=["Composers"],
        summary="List catalogues",
        description="Lista los catálogos (Köchel, BWV, …) desde osap-storage. Se puede filtrar "
        "por prefijo de sigla (?prefix=K) o por compositor (?composer=mozart).",
        response_model=SuccessEnvelope[list[CatalogueRead]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Catalogues", _shared._example([])),
            503: _shared._resp("Storage unavailable", _shared._example({})),
        },
    )
    def list_catalogues(
        response: Response,
        prefix: str | None = Query(default=None),
        composer: str | None = Query(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.catalogues(prefix, composer))
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Storage service is not configured")

    @router.get(
        "/api/v1/composers/{composer_id}/works",
        tags=["Composers"],
        summary="Composer works",
        description="Obras de un compositor. Backend: osap-storage con storage:read.",
        response_model=SuccessEnvelope[ComposerWorksResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Composer works", _shared._example({})),
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def composer_works(
        response: Response,
        composer_id: str,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            detail = ctx.api.get_composer(composer_id)
            if detail is None or not bool(detail.get("visible", True)):
                return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
            return ctx.ok(_shared._composer_works_dto(ctx.api.composer_works(composer_id, limit, offset)))
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Composer service is not configured")

    @router.post(
        "/api/v1/composers/resolve",
        status_code=200,
        tags=["Composers"],
        summary="Resolve a composer identity (read-only)",
        description="Resuelve la identidad de un compositor a partir del contexto (nombre + obra "
        "opcional + fuente + representaciones). No modifica nada en storage: devuelve un veredicto "
        "`resolved | ambiguous | not_found` con confianza, evidencia y candidatos. Nunca inventa "
        "un compositor. No se envía ni devuelve `composer_id`.",
        response_model=SuccessEnvelope[ComposerResolveResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp(
                "Resolved composer identity",
                _shared._example(
                    {
                        "status": "resolved",
                        "composer": {"name": "Wolfgang Amadeus Mozart", "aliases": [], "external_ids": {}},
                        "confidence": 0.9,
                        "input_quality": "normal",
                        "candidates": [],
                        "evidence": [],
                    }
                ),
            ),
            **_shared._standard_errors(422),
        },
    )
    async def resolve_composer(
        payload: ComposerResolveRequest,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        source = payload.source
        reps = [{"title": r.title, "provider": r.provider, "format": r.format} for r in payload.representations]
        decision = await ctx.api.resolve_composer(
            composer=payload.composer.name if payload.composer else None,
            work_title=payload.work.title,
            work_catalog=payload.work.catalog,
            work_year=payload.work.year,
            source_provider=source.provider if source else None,
            source_work_id=source.source_work_id if source else None,
            representations=reps,
        )
        return ctx.ok(_shared._composer_resolve_dto(decision))

    return router
