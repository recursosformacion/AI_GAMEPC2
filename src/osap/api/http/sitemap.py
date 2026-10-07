"""Sitemaps dinámicos: /sitemap.xml (índice) y /sitemaps/{kind}-{page}.xml.

Sin sitemap, Google no descubre las URLs de obra/compositor aunque el HTML sea correcto.
Las URLs se derivan de la misma fuente que las páginas públicas (índice local + osap-storage)
y los ids/slugs son deterministas, así que el sitemap siempre apunta a URLs canónicas.

Se generan bajo demanda y se cachean en memoria con TTL; el tamaño de página (< 50.000,
límite de Google) es configurable por `OSAP_SITEMAP_PAGE_SIZE`.
"""

from __future__ import annotations

import math
import os
import re
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Response

from src.osap.api.seo.render import render_sitemap_index, render_sitemap_urlset
from src.osap.api.seo.slug import person_slug, work_canonical_slug
from src.osap.api.seo.views import (
    canonical_person_url,
    canonical_work_url,
    public_base_url,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.osap.api.http.context import HttpContext

_DEFAULT_PAGE_SIZE = 20000
_MAX_PAGE_SIZE = 50000
# `list_persons` (osap-storage) limita a 500 por página: el sitemap de personas usa su
# propio tamaño para no pedir páginas que el backend rechazaría.
_DEFAULT_PERSONS_PAGE_SIZE = 500
_MAX_PERSONS_PAGE_SIZE = 500
_FILE_CACHE_TTL = 3600
_INDEX_CACHE_TTL = 600
_NAME_RE = re.compile(r"^(works|persons|static)-(\d{1,6})\.xml$")
_LASTMOD_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Landings públicas indexables de la SPA (menú de contenido). Se excluyen las rutas
# internas que nginx marca `noindex` (studio/composer/activity/admin/viewer/resolution/
# candidates/jobs/knowledge/providers/oidc/corrections). Las páginas de entidad
# (/obra, /compositor) van en sus propios sub-sitemaps.
_STATIC_PATHS: tuple[str, ...] = (
    "/",
    "/discover",
    "/explore",
    "/composers",
    "/epochs",
    "/genres",
    "/catalogues",
    "/instruments",
    "/ensembles",
    "/catalog",
    "/sources",
    "/support",
    "/collaborators",
    "/about",
    "/about/how-it-works",
)

_CACHE: dict[str, tuple[float, str]] = {}


def _page_size() -> int:
    raw = os.environ.get("OSAP_SITEMAP_PAGE_SIZE", "")
    size = int(raw) if raw.isdigit() else _DEFAULT_PAGE_SIZE
    return max(1, min(size, _MAX_PAGE_SIZE))


def _persons_page_size() -> int:
    raw = os.environ.get("OSAP_SITEMAP_PERSONS_PAGE_SIZE", "")
    size = int(raw) if raw.isdigit() else _DEFAULT_PERSONS_PAGE_SIZE
    return max(1, min(size, _MAX_PERSONS_PAGE_SIZE))


def _xml(body: str, ttl: int) -> Response:
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Cache-Control": f"public, max-age={ttl}, stale-while-revalidate=86400"},
    )


def _cached(key: str, ttl: int, build: Callable[[], str]) -> str:
    now = time.monotonic()
    entry = _CACHE.get(key)
    if entry is not None and now - entry[0] < ttl:
        return entry[1]
    body = build()
    _CACHE[key] = (now, body)
    return body


def _lastmod(value: object) -> str | None:
    text = str(value or "")
    return text[:10] if _LASTMOD_RE.match(text) else None


def _sitemap_index(ctx: HttpContext) -> str:
    base = public_base_url()
    works_size = _page_size()
    persons_size = _persons_page_size()
    works_pages = math.ceil(ctx.api.sitemap_works_total() / works_size)
    persons_pages = math.ceil(ctx.api.sitemap_persons_total() / persons_size)
    refs = [f"{base}/sitemaps/works-{page}.xml" for page in range(1, works_pages + 1)]
    refs += [f"{base}/sitemaps/persons-{page}.xml" for page in range(1, persons_pages + 1)]
    if _STATIC_PATHS:
        refs.append(f"{base}/sitemaps/static-1.xml")
    return render_sitemap_index(refs)


def _works_urlset(ctx: HttpContext, page: int) -> str:
    size = _page_size()
    rows = ctx.api.sitemap_works_page(size, (page - 1) * size)
    urls: list[tuple[str, str | None]] = []
    for row in rows:
        work_id = str(row.get("work_id") or "")
        title = str(row.get("title") or "")
        if not work_id or not title:
            continue
        urls.append(
            (
                canonical_work_url(work_id, work_canonical_slug(title)),
                _lastmod(row.get("updated_at")),
            )
        )
    return render_sitemap_urlset(urls)


def _persons_urlset(ctx: HttpContext, page: int) -> str:
    size = _persons_page_size()
    rows = ctx.api.sitemap_persons_page(size, (page - 1) * size)
    urls: list[tuple[str, str | None]] = []
    for row in rows:
        person_id = str(row.get("id") or "")
        name = str(row.get("name") or "")
        if not person_id or not name:
            continue
        urls.append((canonical_person_url(person_id, person_slug(name)), None))
    return render_sitemap_urlset(urls)


def _static_urlset(_ctx: HttpContext, page: int) -> str:
    if page != 1:
        return render_sitemap_urlset([])
    base = public_base_url()
    urls: list[tuple[str, str | None]] = [(f"{base}{path}", None) for path in _STATIC_PATHS]
    return render_sitemap_urlset(urls)


def build_sitemap_router(ctx: HttpContext) -> APIRouter:
    router: APIRouter = APIRouter()

    @router.get("/sitemap.xml", include_in_schema=False)
    def sitemap_index() -> Response:
        body = _cached("index", _INDEX_CACHE_TTL, lambda: _sitemap_index(ctx))
        return _xml(body, _INDEX_CACHE_TTL)

    @router.get("/sitemaps/{name}", include_in_schema=False)
    def sitemap_file(name: str) -> Response:
        match = _NAME_RE.fullmatch(name)
        if match is None:
            return Response(status_code=404)
        kind, page = match.group(1), int(match.group(2))
        if page < 1:
            return Response(status_code=404)
        key = f"{kind}-{page}"

        def build() -> str:
            if kind == "works":
                return _works_urlset(ctx, page)
            if kind == "persons":
                return _persons_urlset(ctx, page)
            return _static_urlset(ctx, page)

        body = _cached(key, _FILE_CACHE_TTL, build)
        # Una página fuera de rango no produce <url>: no debe cachearse como vacía válida.
        if "<url>" not in body:
            _CACHE.pop(key, None)
            return Response(status_code=404)
        return _xml(body, _FILE_CACHE_TTL)

    return router
