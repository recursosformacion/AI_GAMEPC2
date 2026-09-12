"""Router OMR: descarga proxy con nombre legible (F5.5-clean)."""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from fastapi import APIRouter, Response

if TYPE_CHECKING:
    from src.osap.api.contracts import ErrorEnvelope
    from src.osap.api.http.context import HttpContext


def build_omr_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/omr/download",
        tags=["Works"],
        summary="Descarga OMR con nombre legible (compositor - título)",
        description=(
            "Proxy de descarga para representaciones OMR conocidas: recibe la URL real "
            "del fichero (storage/R2), la descarga el servidor y la devuelve con "
            "Content-Disposition usando el título de la obra (no el hash). Hosts "
            "permitidos: solo storage propio."
        ),
        response_model=None,
    )
    async def omr_download(
        url: str,
        title: str | None = None,
        composer: str | None = None,
        response: Response = None,  # type: ignore[assignment]
    ) -> Response | ErrorEnvelope:
        parsed = urllib.parse.urlparse(url)
        allowed = {
            "127.0.0.1",
            "localhost",
            "osap-storage",
            "storage.openmusicrepository.com",
            "cdn.openmusicrepository.com",
        }
        if parsed.scheme not in ("http", "https") or parsed.hostname not in allowed:
            return ctx.fail(400, response, "INVALID_URL", "URL no permitida")
        try:
            upstream = requests.get(url, timeout=120, headers=_shared._BROWSER_FETCH_HEADERS)
        except requests.RequestException:
            return ctx.fail(502, response, "UPSTREAM_ERROR", "No se pudo obtener el fichero")
        if upstream.status_code != 200:
            return ctx.fail(502, response, "UPSTREAM_ERROR", "No se pudo obtener el fichero")
        parts = [p for p in (composer, title) if p]
        stem = " - ".join(parts).replace('"', "").strip()
        stem = re.sub(r"[\\/:*?<>|]+", "-", stem).strip() or "obra"
        ext = Path(parsed.path).suffix or ".mxl"
        filename = f"{stem}{ext}"
        encoded = urllib.parse.quote(filename)
        return Response(
            content=upstream.content,
            media_type=upstream.headers.get("content-type") or "application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
        )

    return router
