"""Router de works (F5.5)."""

from __future__ import annotations

import re
import threading
from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Response

from src.osap.api.contracts import (
    ErrorEnvelope,
    ResolutionSessionCreated,
    ResolutionSessionCreateRequest,
    SuccessEnvelope,
)
from src.osap.infrastructure.persistence.storage_vote_store import StorageUnavailableError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext

_FILE_ID_RE = re.compile(r"(\d+)/?$")


def _merge_index_resources(ctx: HttpContext, doc: dict[str, object]) -> None:
    """Añade a `doc['resources']` las reps del ÍNDICE del mismo título.

    Storage guarda un recurso por obra; el índice puede tener varias representaciones de la
    misma pieza (varios ficheros). Así el detalle muestra todas (no solo la de storage).
    Los recursos se expresan con `file_id` numérico, que el backend resuelve al descargar.
    """
    resources = doc.get("resources")
    work = doc.get("work")
    if not isinstance(resources, list) or not isinstance(work, dict):
        return
    title = str(work.get("title") or "")
    composer = str(work.get("composer") or "") or None
    if not title:
        return
    existing = {
        r.get("file_id") for r in resources if isinstance(r, dict) and r.get("file_id") is not None
    }
    try:
        extra = ctx.api.index_representations_for(title, composer)
    except Exception:  # noqa: BLE001 — el detalle nunca debe fallar por el índice
        return
    for rep in extra:
        match = _FILE_ID_RE.search(str(rep.get("download_url") or ""))
        if match is None:
            continue
        file_id = int(match.group(1))
        if file_id in existing:
            continue
        existing.add(file_id)
        resources.append(
            {
                "relative_path": None,
                "format": str(rep.get("format") or "MusicXML"),
                "file_id": file_id,
                "available": True,
                "url": str(rep.get("download_url") or ""),
            }
        )


def build_works_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/works/{work_id}",
        tags=["Composers"],
        summary="Work detail (inspection)",
        description="Detalle completo de una obra (work + resources) para inspección administrativa.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("Work detail", _shared._example({})),
            404: _shared._NOT_FOUND_404,
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def get_work(work_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            doc = ctx.api.get_work(work_id)
        except StorageUnavailableError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Works service is not configured")
        if doc is None:
            return ctx.fail(404, response, "NOT_FOUND", "Work not found")
        _merge_index_resources(ctx, doc)
        return ctx.ok(doc)

    @router.post(
        "/api/v1/works/resolve",
        status_code=202,
        tags=["Works"],
        summary="Create a resolution session (non-blocking)",
        description="Crea una ResolutionSession (ADR-0033) y devuelve session_id "
        "inmediatamente (202). La adquisición/resolución ocurre en el worker de "
        "domain/jobs en segundo plano. Se consulta el progreso con GET "
        "/sessions/{id} y los resultados con GET /sessions/{id}/results. No modifica "
        "storage y no es un catálogo.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            202: _shared._resp("Session created", _shared._example(_shared._resolution_session_created_example())),
            **_shared._standard_errors(422),
        },
    )
    async def resolve_works(
        payload: ResolutionSessionCreateRequest,
        response: Response,
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        works = [w.model_dump() for w in payload.works] if payload.works else None
        created = ctx.api.create_resolution_session(
            query=payload.query,
            works=works,
            providers=list(payload.providers) if payload.providers else None,
            policy=payload.policy.model_dump() if payload.policy else None,
        )
        session_id = cast("str", created["session_id"])
        # Dispara el worker en segundo plano: la adquisición+validación NO bloquea la
        # petición HTTP. El progreso se consulta con GET /sessions/{id}.
        threading.Thread(
            target=ctx.api.resolve_session,
            args=(session_id,),
            name=f"resolve-{session_id[:8]}",
            daemon=True,
        ).start()
        return ctx.ok(
            ResolutionSessionCreated(
                session_id=session_id,
                status=cast("str", created["status"]),
                created_at=cast("str", created["created_at"]),
                expires_at=cast("str", created["expires_at"]),
            )
        )

    return router
