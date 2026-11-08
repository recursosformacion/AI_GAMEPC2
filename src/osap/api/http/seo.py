"""Router público SEO: HTML server-rendered para compositor y obra.

Estas rutas NO forman parte de `/api`: son la salida indexable del catálogo. nginx (y el
proxy de desarrollo) las enruta a osap-api; el resto de la app sigue siendo la SPA React.
La identidad viaja en el id; el slug es descriptivo y un slug distinto redirige 301 al
canónico, de modo que el enlace permanente nunca se rompe.
"""

from __future__ import annotations

import os
import re
import urllib.parse
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
    set_render_flags,
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
_NO_STORE = False

# Las consultas de ficha se cuentan solo para personas: los rastreadores no inflan el ranking.
_BOT_UA = re.compile(
    r"bot|crawl|spider|slurp|bingpreview|facebookexternalhit|headless|lighthouse|preview",
    re.IGNORECASE,
)


def _html(body: str, status_code: int = 200, *, no_store: bool = False) -> HTMLResponse:
    cache = (
        "no-store, no-cache, must-revalidate"
        if _NO_STORE or no_store
        else _CACHE_CONTROL
    )
    return HTMLResponse(
        content=body,
        status_code=status_code,
        headers={"Cache-Control": cache},
    )


def _work_slug(data: dict[str, object]) -> str:
    return work_canonical_slug(str(data.get("title") or "")) or "obra"


def _legacy_redirect(ctx: HttpContext, canonical: str) -> str | None:
    """Return a 301 target when an old id has exactly one current equivalent."""
    target = ctx.api.seo_legacy_target(canonical)
    if not target:
        return None
    target_data = ctx.api.seo_work(target)
    if not isinstance(target_data, dict):
        return None
    return f"/obras/{target}/{_work_slug(target_data)}"


def _resolve_work(
    ctx: HttpContext, canonical: str | None, requested_slug: str | None
) -> tuple[dict[str, object] | None, str | None, bool]:
    """Resolve current/legacy by id *and* slug; never guess on an id alone."""
    if canonical is None:
        return None, None, False
    api = ctx.api
    current = api.seo_work(canonical)
    legacy = api.seo_work_legacy(canonical)
    current_data = current if isinstance(current, dict) else None
    legacy_data = legacy if isinstance(legacy, dict) else None
    current_slug = _work_slug(current_data) if current_data else None
    legacy_slug = _work_slug(legacy_data) if legacy_data else None
    current_match = bool(requested_slug and current_slug == requested_slug)
    legacy_match = bool(requested_slug and legacy_slug == requested_slug)

    if current_match:
        return current_data, None, False
    if legacy_match:
        target = _legacy_redirect(ctx, canonical)
        if target:
            return current_data if current_data else legacy_data, target, True
        return legacy_data, None, True
    if current_data and requested_slug and requested_slug != current_slug:
        # An old ID may collide with a new ID. If the requested slug does not
        # belong to the new work, prefer the old->new alias when available.
        target = api.seo_alias_target(canonical)
        if target:
            target_data = api.seo_work(target)
            if isinstance(target_data, dict):
                return target_data, f"/obras/{target}/{_work_slug(target_data)}", False
    if current_data and legacy_data:
        # The same numeric id exists in both generations and the requested slug
        # matches neither: do not redirect to a potentially unrelated work.
        return None, None, False
    if not current_data and not legacy_data:
        target = api.seo_alias_target(canonical)
        if target:
            target_data = api.seo_work(target)
            if isinstance(target_data, dict):
                return target_data, f"/obras/{target}/{_work_slug(target_data)}", False
    if current_data:
        return current_data, f"/obras/{canonical}/{current_slug}", False
    if legacy_data:
        target = _legacy_redirect(ctx, canonical)
        if target:
            return legacy_data, target, True
        return legacy_data, f"/obras/{canonical}/{legacy_slug}", True
    return None, None, False


def build_seo_router(ctx: HttpContext) -> APIRouter:
    global _NO_STORE
    router: APIRouter = APIRouter()
    storage_info = getattr(ctx.api, "storage_info", None)
    read_only = bool(storage_info()[1]) if callable(storage_info) else False
    mode_fn = getattr(ctx.api, "mode", None)
    mode = mode_fn() if callable(mode_fn) else "unknown"
    blog_base = os.environ.get("OSAP_BLOG_URL", "").rstrip("/") or (
        "https://blog.openmusicrepository.com"
        if mode == "prod"
        else "http://osap-blog"
    )
    # En desarrollo el HTML no se cachea: si no, el navegador sigue mostrando la
    # plantilla anterior durante una hora tras cada cambio.
    _NO_STORE = mode != "prod"
    set_render_flags(read_only=read_only)

    @router.get("/obras/{work_id}", include_in_schema=False)
    def work_canonical(work_id: str) -> Response:
        canonical = normalize_work_id(work_id)
        data, redirect, _ = _resolve_work(ctx, canonical, None)
        if data is None:
            return _html(render_not_found(), status_code=404)
        if redirect:
            return RedirectResponse(url=redirect, status_code=301)
        slug = _work_slug(data)
        return RedirectResponse(url=f"/obras/{canonical}/{slug}", status_code=301)

    @router.get("/obras/{work_id}/{slug}", include_in_schema=False)
    def work_page(work_id: str, slug: str, request: Request) -> Response:
        canonical = normalize_work_id(work_id)
        data, redirect, _ = _resolve_work(ctx, canonical, slug)
        if data is None:
            return _html(render_not_found(), status_code=404)
        if redirect:
            return RedirectResponse(url=redirect, status_code=301)
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
    def composers_list(page: int = 1, q: str | None = None) -> Response:
        per_page = 30
        current = max(1, page)
        term = (q or "").strip() or None
        data = ctx.api.list_composers(term, per_page, (current - 1) * per_page, None, public=True)
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
                nationality = str(
                    item.get("nationality") or item.get("biography_nationality") or ""
                ).strip()
                meta = " · ".join(part for part in (nationality, years) if part)
                words = name.split()
                initials = (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()
                wid = str(item.get("id") or "")
                rows.append(
                    {
                        "id": wid,
                        "name": name,
                        "slug": person_slug(name),
                        "years": years or None,
                        "meta": meta or None,
                        "initials": initials,
                        "works_count": counts.get(wid, item.get("works_count", 0)),
                    }
                )
        total = int(str(data.get("total") or 0)) if isinstance(data, dict) else 0
        pages = max(1, (total + per_page - 1) // per_page)
        params: list[str] = []
        if current > 1:
            params.append(f"page={current}")
        if term:
            params.append(f"q={urllib.parse.quote(term)}")
        canonical = f"{public_base_url()}/composers" + (f"?{'&'.join(params)}" if params else "")
        # Pagination must never be served from a browser/CDN cache: after visiting a
        # composer and going back, a cached page would make "Siguiente" repeat old pages.
        return _html(
            render_composers(rows, current, pages, total, canonical, term),
            no_store=True,
        )


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

    # Rutas antiguas (anteriores a la unificación con la app): 301 directo a la nueva
    # URL canónica, resolviendo el id y el slug de una sola vez (sin cadena de redirects).
    @router.get("/obra/{work_id}", include_in_schema=False)
    def work_legacy_root(work_id: str) -> Response:
        canonical = normalize_work_id(work_id)
        data, redirect, _ = _resolve_work(ctx, canonical, None)
        if data is None:
            # No se inventa un destino para un ID histórico que ya no existe.
            return _html(render_not_found(), status_code=410)
        if redirect:
            return RedirectResponse(url=redirect, status_code=301)
        return RedirectResponse(url=f"/obras/{canonical}/{_work_slug(data)}", status_code=301)

    @router.get("/obra/{work_id}/{slug}", include_in_schema=False)
    def work_legacy_page(work_id: str, slug: str) -> Response:
        canonical = normalize_work_id(work_id)
        data, redirect, _ = _resolve_work(ctx, canonical, slug)
        if data is None:
            return _html(render_not_found(), status_code=410)
        if redirect:
            return RedirectResponse(url=redirect, status_code=301)
        return RedirectResponse(url=f"/obras/{canonical}/{_work_slug(data)}", status_code=301)

    @router.get("/compositor/{person_id}", include_in_schema=False)
    def person_legacy_root(person_id: str) -> Response:
        # Los UUID de persona son estables; el 301 conserva las URLs antiguas.
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

    def blog_article_redirect(data: dict[str, object], fallback_slug: str) -> RedirectResponse | None:
        if str(data.get("group_id") or ""):
            return None
        slug = str(data.get("slug") or fallback_slug)
        return RedirectResponse(
            url=f"{blog_base}/blog/{urllib.parse.quote(slug)}",
            status_code=301,
        )

    @router.get("/amigos/articulos", include_in_schema=False)
    def amigos_articles_home() -> Response:
        return RedirectResponse(url=f"{blog_base}/", status_code=301)

    @router.get("/amigos/articulo/{article_id}", include_in_schema=False)
    def amigos_article_canonical(article_id: str) -> Response:
        data = ctx.api.seo_amigos_article(article_id)
        if data is None:
            return _html(render_not_found(), status_code=404)
        view = build_article_view(data)
        redirect = blog_article_redirect(data, view.slug)
        if redirect is not None:
            return redirect
        return RedirectResponse(url=f"/amigos/articulo/{article_id}/{view.slug}", status_code=301)

    @router.get("/amigos/articulo/{article_id}/{slug}", include_in_schema=False)
    def amigos_article_page(article_id: str, slug: str) -> Response:
        data = ctx.api.seo_amigos_article(article_id)
        if data is None:
            return _html(render_not_found(), status_code=404)
        view = build_article_view(data)
        redirect = blog_article_redirect(data, view.slug)
        if redirect is not None:
            return redirect
        if slug != view.slug:
            return RedirectResponse(url=f"/amigos/articulo/{article_id}/{view.slug}", status_code=301)
        return _html(render_amigos_article(view))

    return router

