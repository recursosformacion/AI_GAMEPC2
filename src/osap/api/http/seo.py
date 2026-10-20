"""Router público SEO: HTML server-rendered para compositor y obra.

Estas rutas NO forman parte de `/api`: son la salida indexable del catálogo. nginx (y el
proxy de desarrollo) las enruta a osap-api; el resto de la app sigue siendo la SPA React.
La identidad viaja en el id; el slug es descriptivo y un slug distinto redirige 301 al
canónico, de modo que el enlace permanente nunca se rompe.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from src.osap.api.seo.render import (
    render_amigos_article,
    render_amigos_group,
    render_composers,
    render_not_found,
    render_person,
    render_representation,
    render_work,
)
from src.osap.api.seo.slug import normalize_work_id, person_slug, work_canonical_slug
from src.osap.api.seo.views import (
    build_person_view,
    build_representation_payload,
    build_work_view,
    public_base_url,
)
from src.osap.api.seo.views_amigos import build_article_view, build_group_view

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext

_CACHE_CONTROL = "public, max-age=3600, stale-while-revalidate=86400"

# Las consultas de ficha se cuentan solo para personas: los rastreadores no inflan el ranking.
_BOT_UA = re.compile(
    r"bot|crawl|spider|slurp|bingpreview|facebookexternalhit|headless|lighthouse|preview",
    re.IGNORECASE,
)


def _html(body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        content=body,
        status_code=status_code,
        headers={"Cache-Control": _CACHE_CONTROL},
    )


def build_seo_router(ctx: HttpContext) -> APIRouter:
    router: APIRouter = APIRouter()

    @router.get("/obras/{work_id}", include_in_schema=False)
    def work_canonical(work_id: str) -> Response:
        canonical = normalize_work_id(work_id)
        data = ctx.api.seo_work(canonical) if canonical is not None else None
        if data is None:
            return _html(render_not_found(), status_code=404)
        slug = work_canonical_slug(str(data.get("title") or ""))
        return RedirectResponse(url=f"/obras/{canonical}/{slug}", status_code=301)

    @router.get("/obras/{work_id}/{slug}", include_in_schema=False)
    def work_page(work_id: str, slug: str, request: Request) -> Response:
        canonical = normalize_work_id(work_id)
        data = ctx.api.seo_work(canonical) if canonical is not None else None
        if data is None:
            return _html(render_not_found(), status_code=404)
        expected = work_canonical_slug(str(data.get("title") or ""))
        if slug != expected:
            return RedirectResponse(url=f"/obras/{canonical}/{expected}", status_code=301)
        related: list[dict[str, object]] = []
        composer_id = data.get("composer_id")
        composer_page = False
        if isinstance(composer_id, str) and composer_id:
            composer_page = ctx.api.seo_person(composer_id) is not None
            siblings = ctx.api.seo_person_works(composer_id, 8, 0)
            items = siblings.get("items")
            if isinstance(items, list):
                related = [item for item in items if isinstance(item, dict)]
        # Consulta real (personas): alimenta «Obras más consultadas» de la portada.
        if canonical is not None and not _BOT_UA.search(request.headers.get("user-agent", "")):
            ctx.api.record_work_consult(work_id=canonical)
        return _html(render_work(build_work_view(data, related, composer_page=composer_page)))

    @router.get("/representacion/{rep_id}", include_in_schema=False)
    def representation_page(rep_id: str) -> Response:
        info = ctx.api.get_representation_download(rep_id)
        payload = (
            build_representation_payload(info, rep_id) if isinstance(info, dict) else None
        )
        if payload is None:
            return _html(render_not_found(), status_code=404)
        return _html(render_representation(payload))

    @router.get("/composers", include_in_schema=False)
    def composers_list(page: int = 1) -> Response:
        per_page = 50
        current = max(1, page)
        data = ctx.api.list_composers(None, per_page, (current - 1) * per_page, None, public=True)
        items = data.get("items") if isinstance(data, dict) else None
        rows: list[dict[str, object]] = []
        if isinstance(items, list):
            ids = [str(i.get("id")) for i in items if isinstance(i, dict) and i.get("id")]
            counts = ctx.api.index_works_counts(ids)
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                birth = str(item.get("birth_year") or "").strip()
                death = str(item.get("death_year") or "").strip()
                years = f"{birth}–{death}" if birth and death else (birth or death)
                wid = str(item.get("id") or "")
                rows.append(
                    {
                        "id": wid,
                        "name": name,
                        "slug": person_slug(name),
                        "years": years or None,
                        "works_count": counts.get(wid, item.get("works_count", 0)),
                    }
                )
        total = int(data.get("total") or 0) if isinstance(data, dict) else 0
        pages = max(1, (total + per_page - 1) // per_page)
        canonical = f"{public_base_url()}/composers" + (f"?page={current}" if current > 1 else "")
        return _html(render_composers(rows, current, pages, total, canonical))

    @router.get("/composers/{person_id}", include_in_schema=False)
    def person_canonical(person_id: str) -> Response:
        detail = ctx.api.seo_person(person_id)
        if detail is None:
            return _html(render_not_found(), status_code=404)
        slug = person_slug(str(detail.get("name") or ""))
        return RedirectResponse(url=f"/composers/{person_id}/{slug}", status_code=301)

    @router.get("/composers/{person_id}/{slug}", include_in_schema=False)
    def person_page(person_id: str, slug: str) -> Response:
        detail = ctx.api.seo_person(person_id)
        if detail is None:
            return _html(render_not_found(), status_code=404)
        expected = person_slug(str(detail.get("name") or ""))
        if slug != expected:
            return RedirectResponse(url=f"/composers/{person_id}/{expected}", status_code=301)
        works = ctx.api.seo_person_works(person_id, 300, 0)
        return _html(render_person(build_person_view(detail, works)))

    # Rutas antiguas (anteriores a la unificación con la app): 301 a las nuevas con slug.
    @router.get("/obra/{work_id}", include_in_schema=False)
    def work_legacy_root(work_id: str) -> Response:
        return RedirectResponse(url=f"/obras/{work_id}", status_code=301)

    @router.get("/obra/{work_id}/{slug}", include_in_schema=False)
    def work_legacy_page(work_id: str, slug: str) -> Response:
        return RedirectResponse(url=f"/obras/{work_id}/{slug}", status_code=301)

    @router.get("/compositor/{person_id}", include_in_schema=False)
    def person_legacy_root(person_id: str) -> Response:
        return RedirectResponse(url=f"/composers/{person_id}", status_code=301)

    @router.get("/compositor/{person_id}/{slug}", include_in_schema=False)
    def person_legacy_page(person_id: str, slug: str) -> Response:
        return RedirectResponse(url=f"/composers/{person_id}/{slug}", status_code=301)

    # --- «Los amigos» (grupo y artículo) -------------------------------------

    @router.get("/amigos/corales/{group_id}", include_in_schema=False)
    def amigos_group_canonical(group_id: str) -> Response:
        data = ctx.api.seo_amigos_group(group_id)
        if data is None:
            return _html(render_not_found(), status_code=404)
        view = build_group_view(data)
        return RedirectResponse(url=f"/amigos/corales/{group_id}/{view.slug}", status_code=301)

    @router.get("/amigos/corales/{group_id}/{slug}", include_in_schema=False)
    def amigos_group_page(group_id: str, slug: str) -> Response:
        data = ctx.api.seo_amigos_group(group_id)
        if data is None:
            return _html(render_not_found(), status_code=404)
        view = build_group_view(data)
        if slug != view.slug:
            return RedirectResponse(url=f"/amigos/corales/{group_id}/{view.slug}", status_code=301)
        return _html(render_amigos_group(view))

    @router.get("/amigos/articulo/{article_id}", include_in_schema=False)
    def amigos_article_canonical(article_id: str) -> Response:
        data = ctx.api.seo_amigos_article(article_id)
        if data is None:
            return _html(render_not_found(), status_code=404)
        view = build_article_view(data)
        return RedirectResponse(url=f"/amigos/articulo/{article_id}/{view.slug}", status_code=301)

    @router.get("/amigos/articulo/{article_id}/{slug}", include_in_schema=False)
    def amigos_article_page(article_id: str, slug: str) -> Response:
        data = ctx.api.seo_amigos_article(article_id)
        if data is None:
            return _html(render_not_found(), status_code=404)
        view = build_article_view(data)
        if slug != view.slug:
            return RedirectResponse(url=f"/amigos/articulo/{article_id}/{view.slug}", status_code=301)
        return _html(render_amigos_article(view))

    return router
