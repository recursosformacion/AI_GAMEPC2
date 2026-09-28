"""Tests del sitemap dinámico (/sitemap.xml y /sitemaps/*.xml)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.http import sitemap as sitemap_module
from src.osap.api.http.context import HttpContext
from src.osap.api.http.sitemap import build_sitemap_router

_BASE = "https://app.openmusicrepository.com"

_WORKS = [
    {"work_id": "index-1", "title": "Ave verum corpus", "updated_at": "2026-01-02T10:00:00"},
    {"work_id": "index-2", "title": "Anónimo", "updated_at": None},
    {"work_id": "index-3", "title": "Réquiem", "updated_at": "2026-01-03"},
]
_PERSONS = [{"id": "person-1", "name": "Wolfgang Amadeus Mozart"}]


class _FakeApi:
    def sitemap_works_total(self) -> int:
        return len(_WORKS)

    def sitemap_works_page(self, limit: int, offset: int) -> list[dict[str, object]]:
        return _WORKS[offset : offset + limit]

    def sitemap_persons_total(self) -> int:
        return len(_PERSONS)

    def sitemap_persons_page(self, limit: int, offset: int) -> list[dict[str, object]]:
        return _PERSONS[offset : offset + limit]


@pytest.fixture(autouse=True)
def _fixed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSAP_PUBLIC_BASE_URL", _BASE)
    monkeypatch.delenv("OSAP_SITEMAP_PAGE_SIZE", raising=False)
    sitemap_module._CACHE.clear()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(build_sitemap_router(HttpContext(api=_FakeApi(), container=object())))  # type: ignore[arg-type]
    return TestClient(app)


def test_sitemap_index_referencia_las_paginas(client: TestClient) -> None:
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "<sitemapindex" in resp.text
    assert f"<loc>{_BASE}/sitemaps/works-1.xml</loc>" in resp.text
    assert f"<loc>{_BASE}/sitemaps/persons-1.xml</loc>" in resp.text


def test_sitemap_works_urls_canonicas_y_lastmod(client: TestClient) -> None:
    resp = client.get("/sitemaps/works-1.xml")
    assert resp.status_code == 200
    assert "<urlset" in resp.text
    assert f"<loc>{_BASE}/obra/index-1/ave-verum-corpus</loc>" in resp.text
    assert "<lastmod>2026-01-02</lastmod>" in resp.text
    assert f"<loc>{_BASE}/obra/index-2/anonimo</loc>" in resp.text
    assert f"<loc>{_BASE}/obra/index-3/requiem</loc>" in resp.text


def test_sitemap_persons_urls_canonicas(client: TestClient) -> None:
    resp = client.get("/sitemaps/persons-1.xml")
    assert resp.status_code == 200
    assert f"<loc>{_BASE}/compositor/person-1/wolfgang-amadeus-mozart</loc>" in resp.text


def test_pagina_fuera_de_rango_404(client: TestClient) -> None:
    assert client.get("/sitemaps/works-2.xml").status_code == 404


def test_nombre_invalido_404(client: TestClient) -> None:
    assert client.get("/sitemaps/bogus-1.xml").status_code == 404
    assert client.get("/sitemaps/works-0.xml").status_code == 404


def test_page_size_configurable(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("OSAP_SITEMAP_PAGE_SIZE", "2")
    resp = client.get("/sitemap.xml")
    assert f"<loc>{_BASE}/sitemaps/works-2.xml</loc>" in resp.text
    assert client.get("/sitemaps/works-2.xml").status_code == 200
