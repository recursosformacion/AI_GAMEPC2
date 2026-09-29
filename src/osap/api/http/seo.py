"""Router público SEO: HTML server-rendered para compositor y obra.

Estas rutas NO forman parte de `/api`: son la salida indexable del catálogo. nginx (y el
proxy de desarrollo) las enruta a osap-api; el resto de la app sigue siendo la SPA React.
La identidad viaja en el id; el slug es descriptivo y un slug distinto redirige 301 al
canónico, de modo que el enlace permanente nunca se rompe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from src.osap.api.seo.render import render_not_found, render_person, render_work
from src.osap.api.seo.slug import normalize_work_id, person_slug, work_canonical_slug
from src.osap.api.seo.views import build_person_view, build_work_view

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext

_CACHE_CONTROL = "public, max-age=3600, stale-while-revalidate=86400"


def _html(body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        content=body,
        status_code=status_code,
        headers={"Cache-Control": _CACHE_CONTROL},
    )


def build_seo_router(ctx: HttpContext) -> APIRouter:
    router: APIRouter = APIRouter()

    @router.get("/obra/{work_id}", include_in_schema=False)
    def work_canonical(work_id: str) -> Response:
        canonical = normalize_work_id(work_id)
        data = ctx.api.seo_work(canonical) if canonical is not None else None
        if data is None:
            return _html(render_not_found(), status_code=404)
        slug = work_canonical_slug(str(data.get("title") or ""), str(data.get("composer") or "") or None)
        return RedirectResponse(url=f"/obra/{canonical}/{slug}", status_code=301)

    @router.get("/obra/{work_id}/{slug}", include_in_schema=False)
    def work_page(work_id: str, slug: str) -> Response:
        canonical = normalize_work_id(work_id)
        data = ctx.api.seo_work(canonical) if canonical is not None else None
        if data is None:
            return _html(render_not_found(), status_code=404)
        expected = work_canonical_slug(str(data.get("title") or ""), str(data.get("composer") or "") or None)
        if slug != expected:
            return RedirectResponse(url=f"/obra/{canonical}/{expected}", status_code=301)
        related: list[dict[str, object]] = []
        composer_id = data.get("composer_id")
        if isinstance(composer_id, str) and composer_id:
            siblings = ctx.api.seo_person_works(composer_id, 8, 0)
            items = siblings.get("items")
            if isinstance(items, list):
                related = [item for item in items if isinstance(item, dict)]
        return _html(render_work(build_work_view(data, related)))

    @router.get("/compositor/{person_id}", include_in_schema=False)
    def person_canonical(person_id: str) -> Response:
        detail = ctx.api.seo_person(person_id)
        if detail is None:
            return _html(render_not_found(), status_code=404)
        slug = person_slug(str(detail.get("name") or ""))
        return RedirectResponse(url=f"/compositor/{person_id}/{slug}", status_code=301)

    @router.get("/compositor/{person_id}/{slug}", include_in_schema=False)
    def person_page(person_id: str, slug: str) -> Response:
        detail = ctx.api.seo_person(person_id)
        if detail is None:
            return _html(render_not_found(), status_code=404)
        expected = person_slug(str(detail.get("name") or ""))
        if slug != expected:
            return RedirectResponse(url=f"/compositor/{person_id}/{expected}", status_code=301)
        works = ctx.api.seo_person_works(person_id, 300, 0)
        return _html(render_person(build_person_view(detail, works)))

    return router
