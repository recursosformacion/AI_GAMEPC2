"""Espacio de trabajo personal: fachada server-side a Chorus.

Chorus es el dueño de la biblioteca personal. Aquí solo se reenvía la petición con
el token del usuario; Chorus valida la sesión con osap-auth. El navegador nunca
conoce la URL interna de Chorus ni recibe otro token que el suyo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests
from fastapi import APIRouter, Header, Response
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext

_TIMEOUT = 10


def build_workspace_router(ctx: HttpContext) -> APIRouter:
    router = APIRouter()

    def _error(status: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={"success": False, "error": {"code": code, "message": message}},
        )

    def _forward(
        method: str,
        path: str,
        authorization: str | None,
        *,
        body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        if not authorization:
            return _error(401, "UNAUTHORIZED", "Falta la sesión de OSAP")
        base = (ctx.container.chorus_api_base() or "").rstrip("/")
        if not base:
            return _error(503, "WORKSPACE_UNAVAILABLE", "Espacio de trabajo no configurado")
        try:
            upstream = requests.request(
                method,
                f"{base}{path}",
                json=body,
                params=params,
                headers={"Authorization": authorization},
                timeout=_TIMEOUT,
            )
        except requests.RequestException:
            return _error(503, "WORKSPACE_UNAVAILABLE", "Espacio de trabajo no disponible")
        if upstream.status_code >= 400:
            try:
                payload = upstream.json()
            except ValueError:
                payload = None
            detail = ""
            if isinstance(payload, dict):
                detail = str(payload.get("detail") or payload.get("message") or "")
            status = upstream.status_code if upstream.status_code in (400, 401, 403, 404, 409, 422) else 502
            return _error(status, "WORKSPACE_ERROR", detail or "No se pudo completar la operación")
        if upstream.status_code == 204:
            return Response(status_code=204)
        try:
            data = upstream.json()
        except ValueError:
            return _error(502, "INVALID_RESPONSE", "El espacio de trabajo devolvió una respuesta inválida")
        return JSONResponse(
            status_code=upstream.status_code,
            content={"success": True, "data": data},
        )

    @router.get("/api/v1/workspace/library", tags=["Workspace"])
    def library(
        q: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> Response:
        """Biblioteca personal del usuario, opcionalmente filtrada por texto."""
        return _forward(
            "GET",
            "/api/v1/library",
            authorization,
            params={"q": q} if q else None,
        )

    @router.post("/api/v1/workspace/library", tags=["Workspace"])
    def save_reference(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> Response:
        """Guarda una referencia (obra + representación) en la biblioteca personal."""
        return _forward("POST", "/api/v1/library/references", authorization, body=payload)

    @router.delete("/api/v1/workspace/library/{item_id}", tags=["Workspace"])
    def remove_reference(
        item_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        return _forward("DELETE", f"/api/v1/library/{item_id}", authorization)

    return router
