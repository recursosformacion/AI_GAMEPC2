"""Router de sessions (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Response

from src.osap.api.contracts import (
    ErrorEnvelope,
    RepresentationSelectionRead,
    RepresentationSelectRequest,
    SuccessEnvelope,
)

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_sessions_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/sessions/{session_id}",
        status_code=200,
        tags=["Works"],
        summary="Get resolution session state",
        description="Estado + progreso + contadores de una ResolutionSession. `expired` "
        "devuelve 200 (la sesión existió pero caducó); 404 solo si el session_id es "
        "desconocido o fue eliminado por el TTL.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Session state", _shared._example(_shared._resolution_session_example())),
            **_shared._standard_errors(404),
        },
    )
    async def get_resolution_session(
        session_id: str,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        data = ctx.api.get_resolution_session(session_id)
        if data is None:
            return ctx.fail(404, response, "NOT_FOUND", "Resolution session not found")
        return ctx.ok(_shared._resolution_session_dto(data))

    @router.get(
        "/api/v1/sessions/{session_id}/results",
        status_code=200,
        tags=["Works"],
        summary="List resolution session results",
        description="Resultados de resolución (paginación de la Web, desacoplada de la de "
        "proveedores). `resolution_stage` indica provisional/definitive; `revision` sube "
        "cada vez que cambia un resultado.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Results page", _shared._example(_shared._resolution_results_example())),
            **_shared._standard_errors(404),
        },
    )
    async def get_resolution_results(
        session_id: str,
        response: Response,
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=100),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        data = ctx.api.list_resolution_results(session_id, page=page, per_page=per_page)
        if data is None:
            return ctx.fail(404, response, "NOT_FOUND", "Resolution session not found")
        return ctx.ok(_shared._resolution_results_dto(data))

    @router.get(
        "/api/v1/sessions/{session_id}/score-contract",
        status_code=200,
        tags=["Works"],
        summary="Produce el ScoreContract de una sesión resuelta",
        description=(
            "Productor OSAP → Chorus: para una sesión ya terminada con representación "
            "seleccionada (obra identificada + mejor representación), revalida esa "
            "representación y devuelve el `ScoreContract` serializable (JSON). El "
            "consumidor de Chorus lo recibe en `POST /generate`."
        ),
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("ScoreContract", {"score_contract": {"schema_version": 1}}),
            **_shared._standard_errors(404, 409, 422, 502),
        },
    )
    async def get_session_score_contract(
        session_id: str,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        code, err_code, message, payload = ctx.api.score_contract_for_session(session_id)
        if code == 200 and payload is not None:
            return ctx.ok(payload)
        if code in (404, 409, 422, 502):
            return ctx.fail(code, response, err_code, message)
        return ctx.fail(500, response, "INTERNAL", "No se pudo generar el contrato")

    @router.post(
        "/api/v1/works/{work_id}/representations/select-best",
        tags=["Works"],
        summary="Select best representation among the KNOWN ones of a work",
        description=(
            "Recibe la lista de representaciones ya conocidas de la Work (la misma que "
            "muestra la UI) y selecciona la mejor con BestRepresentationSelector, "
            "persistiéndola POR WORK. NO adquiere ni consulta proveedores."
        ),
        response_model=SuccessEnvelope[RepresentationSelectionRead] | ErrorEnvelope,
        responses={200: _shared._resp("Selection", _shared._example({})), **_shared._standard_errors(422)},
    )
    async def select_best_representation_route(
        work_id: str,
        payload: RepresentationSelectRequest,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        result = ctx.api.select_best_representation(work_id, payload.representations)
        return ctx.ok(result)

    @router.get(
        "/api/v1/works/{work_id}/representations/selection",
        tags=["Works"],
        summary="Persisted selected representation of a work",
        response_model=SuccessEnvelope[RepresentationSelectionRead] | ErrorEnvelope,
        responses={200: _shared._resp("Selection", _shared._example({})), **_shared._standard_errors(404)},
    )
    async def get_selected_representation_route(
        work_id: str,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        selection = ctx.api.get_work_selection(work_id)
        if selection is None:
            return ctx.ok(
                RepresentationSelectionRead(
                    work_id=work_id,
                    representations_known=0,
                    candidates_usable=0,
                    status="none_selected",
                    message="Sin representación seleccionada.",
                )
            )
        return ctx.ok(selection)

    return router
