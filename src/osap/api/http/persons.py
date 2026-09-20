"""Router de personas (modelo nuevo de osap-storage: `persons` + roles).

`/api/v1/composers` se mantiene (compatibilidad v1) y equivale a `role=composer`. Estos
endpoints exponen el contrato nuevo:

- `GET /api/v1/persons?role=composer[,arranger…]` → lista
- `GET /api/v1/persons/{person_id}` → ficha (con roles y biografía)
- `GET /api/v1/persons/{person_id}/works` → obras

Mientras osap-storage no publique `/persons`, el cliente cae a `/composers` (solo
compositores), de modo que la app sigue funcionando durante la migración.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Response

from src.osap.api.contracts import ErrorEnvelope, SuccessEnvelope
from src.osap.domain.person_roles import parse_roles
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_persons_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/persons",
        tags=["Composers"],
        summary="List persons by role",
        description="Personas del catálogo por rol: `role=composer`, `role=arranger`, "
        "`role=composer,arranger`… Sin `role` se asume `composer` (compatibilidad con "
        "`/composers`). Backend: osap-storage.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Persons", _shared._example({"items": [], "total": 0})),
            400: _shared._resp("Unknown role", _shared._example({})),
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def list_persons(
        response: Response,
        role: str | None = Query(default=None, description="composer,arranger,…"),
        q: str | None = Query(default=None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        review: str | None = Query(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            roles = parse_roles(role)
        except ValueError as exc:
            return ctx.fail(400, response, "INVALID_REQUEST", str(exc))
        try:
            data = ctx.api.list_persons(roles, q, limit, offset, review)
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Storage service is not configured")
        # Recuento de obras desde el índice local (el catálogo realmente consultable).
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            ids = [str(i.get("id")) for i in items if isinstance(i, dict) and i.get("id")]
            counts = ctx.api.index_works_counts(ids)
            for item in items:
                if isinstance(item, dict) and str(item.get("id") or "") in counts:
                    item["works_count"] = counts[str(item["id"])]
        return ctx.ok(_shared._composer_list_dto(data))

    @router.get(
        "/api/v1/persons/{person_id}",
        tags=["Composers"],
        summary="Person detail",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Person", _shared._example({})),
            404: _shared._resp("Not found", _shared._example({})),
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def get_person(person_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            detail = ctx.api.get_composer_biography(person_id)
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Storage service is not configured")
        if detail is None or not bool(detail.get("visible", True)):
            return ctx.fail(404, response, "NOT_FOUND", "Person not found")
        counts = ctx.api.index_works_counts([str(detail.get("id") or "")])
        if str(detail.get("id") or "") in counts:
            detail["works_count"] = counts[str(detail["id"])]
        return ctx.ok(_shared._composer_detail_dto(detail))

    @router.get(
        "/api/v1/persons/{person_id}/works",
        tags=["Composers"],
        summary="Person works",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Person works", _shared._example({})),
            404: _shared._resp("Not found", _shared._example({})),
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def person_works(
        response: Response,
        person_id: str,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            detail = ctx.api.get_composer(person_id)
            if detail is None or not bool(detail.get("visible", True)):
                return ctx.fail(404, response, "NOT_FOUND", "Person not found")
            return ctx.ok(_shared._composer_works_dto(ctx.api.composer_works(person_id, limit, offset)))
        except StorageComposerError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Storage service is not configured")

    return router
