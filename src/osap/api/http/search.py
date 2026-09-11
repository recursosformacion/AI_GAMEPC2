"""Router de search (F5.5)."""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

import requests
from fastapi import APIRouter, Header, Query, Response
from fastapi.responses import RedirectResponse

from src.osap.api.contracts import (
    ErrorEnvelope,
    IntentResponse,
    SearchModel,
    SearchRequest,
    SearchResponse,
    SuccessEnvelope,
)

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext

_LOCAL_STORAGE_HOSTS = {"127.0.0.1", "localhost"}


def _belongs_to_storage(url: str, storage_base: str) -> bool:
    """True si la URL es de nuestro storage (CDN propio o proxy local de storage)."""
    if storage_base and url.lower().startswith(storage_base.lower()):
        return True
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname in _LOCAL_STORAGE_HOSTS:
        return True
    path = parsed.path.lower()
    return path.startswith("/api/download/") or path.startswith("/api/v1/files/")


def build_search_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/representations/{representation_id}/download",
        tags=["Searches"],
        summary="Download a representation",
        description=(
            "Streams the representation file. Por defecto fuerza descarga (attachment). "
            "Con `?view=1` sirve el fichero inline con su content-type para visualizarlo "
            "directamente en el navegador (p. ej. PDFs)."
        ),
        response_model=None,
    )
    def download_representation(
        representation_id: str,
        response: Response,
        view: int = Query(default=0, ge=0, le=1),
    ) -> Response | ErrorEnvelope:
        info = ctx.api.get_representation_download(representation_id)
        if info is None:
            return ctx.fail(404, response, "NOT_FOUND", "Representation not found")
        url = str(info.get("download_url") or "")
        if not url:
            return ctx.fail(404, response, "NOT_FOUND", "No download available")

        # OMR/OSAP storage: el fichero vive en nuestro storage bajo un nombre hash.
        # En lugar de redirigir (el navegador usaría el hash como nombre), lo servimos
        # desde el servidor con un nombre legible (compositor - título). También tratamos
        # como "nuestro" el storage local (127.0.0.1/localhost, /api/download/, /api/v1/files/)
        # para que `?view=1` pueda servirse inline (PDF en el navegador).
        storage_base = (ctx.container.storage_web_base() or "").rstrip("/")
        url_normalized = url.rstrip("/")

        if _belongs_to_storage(url_normalized, storage_base):
            try:
                upstream = requests.get(url, timeout=120)
            except requests.RequestException:
                return ctx.fail(502, response, "UPSTREAM_ERROR", "No se pudo obtener el fichero del storage")
            if upstream.status_code != 200:
                return ctx.fail(502, response, "UPSTREAM_ERROR", "No se pudo obtener el fichero del storage")

            filename = _shared._download_filename(info)
            # Sanitizar el nombre para Content-Disposition (RFC 5987)
            safe_filename = filename.replace('"', '\\"').replace('\n', '').replace('\r', '')
            disposition = "inline" if view else "attachment"
            fmt = str(info.get("format") or "")
            media_type = _shared._media_type_for_format(fmt)

            encoded_filename = urllib.parse.quote(safe_filename)
            content_disposition = (
                f'{disposition}; filename="{safe_filename}"; '
                f"filename*=UTF-8''{encoded_filename}"
            )

            return Response(
                content=upstream.content,
                media_type=media_type,
                headers={"Content-Disposition": content_disposition},
            )

        # Proveedores externos (IMSLP/MusicBrainz/Mutopia...): el servidor NO proxya
        # porque responden con challenge anti-bot a peticiones de servidor; el navegador
        # del usuario sí las resuelve. Se redirige (302) a la URL del proveedor.
        return RedirectResponse(url, status_code=302)

    @router.get(
        "/api/v1/search-model",
        tags=["Searches"],
        summary="Search model",
        description="Exposes the search criteria/blocks that Search Studio renders.",
        response_model=SuccessEnvelope[SearchModel],
        responses={200: _shared._resp("Search model", _shared._example({}))},
    )
    def search_model() -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.search_model())

    @router.get(
        "/api/v1/intent",
        tags=["Searches"],
        summary="Intent detection",
        description="Classifies a query into an entity (composer, work, catalogue, collection, source).",
        response_model=SuccessEnvelope[IntentResponse],
        responses={200: _shared._resp("Intent", _shared._example({"type": "composer", "label": "Mozart"}))},
    )
    def detect_intent(query: str = "") -> SuccessEnvelope[object]:
        return ctx.ok(ctx.api.detect_intent(query))

    @router.post(
        "/api/v1/searches",
        status_code=201,
        tags=["Searches"],
        summary="Create a search",
        description="Creates a search as a resource. Returns 201 with a Location header.",
        response_model=SuccessEnvelope[SearchResponse] | ErrorEnvelope,
        responses={201: _shared._SEARCH_CREATED_201, **_shared._standard_errors(400)},
    )
    def create_search(
        payload: SearchRequest, response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        del authorization  # auth prepared but disabled in V3.1
        has_query = bool(payload.query and payload.query.strip())
        if not has_query and not payload.composer and not payload.title and not payload.catalogue:
            return ctx.fail(400, response, "INVALID_QUERY", "Query cannot be empty")
        search_id, search = ctx.api.create_search(payload)
        response.headers["Location"] = f"/api/v1/searches/{search_id}"
        return ctx.ok(search)

    @router.get(
        "/api/v1/searches/{search_id}",
        tags=["Searches"],
        summary="Get a search",
        description="Retrieves the result of a previously created search.",
        response_model=SuccessEnvelope[SearchResponse] | ErrorEnvelope,
        responses={200: _shared._SEARCH_GET_200, **_shared._standard_errors(404)},
    )
    def get_search(search_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        search = ctx.api.get_search(search_id)
        if search is None:
            return ctx.fail(404, response, "NOT_FOUND", "Search not found")
        return ctx.ok(search)

    return router
