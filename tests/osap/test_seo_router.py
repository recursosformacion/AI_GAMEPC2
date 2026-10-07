"""Tests del router público SEO (HTML server-rendered de /compositor y /obra)."""

from __future__ import annotations

import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.http.context import HttpContext
from src.osap.api.http.seo import build_seo_router

_BASE = "https://app.openmusicrepository.com"

_WORK: dict[str, object] = {
    "work_id": "index-7",
    "title": "Ave verum corpus",
    "composer": "Wolfgang Amadeus Mozart",
    "composer_id": "person-1",
    "catalogue": "KV 618",
    "year": 1791,
    "instrumentation": "coro",
    "representations": [
        {
            "provider": "omr",
            "format": "musicxml",
            "url": "https://storage.openmusicrepository.com/api/download/9",
            "downloadable": True,
        },
        {
            "provider": "imslp",
            "format": "pdf",
            "url": "https://imslp.org/wiki/Ave_verum",
            "downloadable": False,
        },
    ],
}

_PERSON: dict[str, object] = {
    "id": "person-1",
    "name": "Wolfgang Amadeus Mozart",
    "birth_year": "1756",
    "death_year": "1791",
    "biography_era": "Clasicismo",
    "biography_nationality": "Austria",
    "biography_summary": "Compositor austriaco.",
    "biography_key_works": ["Ave verum corpus"],
    "visible": True,
}

_WORKS: dict[str, object] = {
    "items": [
        {"work_id": "index-7", "title": "Ave verum corpus", "catalogue": "KV 618"},
        {"work_id": "index-8", "title": "Réquiem", "catalogue": None},
    ],
    "total": 2,
}


class _FakeApi:
    def __init__(
        self,
        work: dict[str, object] = _WORK,
        person: dict[str, object] = _PERSON,
        works: dict[str, object] = _WORKS,
    ) -> None:
        self._work = work
        self._person = person
        self._works = works

    def seo_work(self, work_id: str | None) -> dict[str, object] | None:
        return self._work if work_id == self._work.get("work_id") else None

    def seo_person(self, person_id: str) -> dict[str, object] | None:
        return self._person if person_id == self._person.get("id") else None

    def seo_person_works(self, person_id: str, limit: int, offset: int) -> dict[str, object]:
        return self._works if person_id == self._person.get("id") else {"items": [], "total": 0}


def _client(api: _FakeApi) -> TestClient:
    app = FastAPI()
    app.include_router(build_seo_router(HttpContext(api=api, container=object())))  # type: ignore[arg-type]
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fixed_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSAP_PUBLIC_BASE_URL", _BASE)


@pytest.fixture()
def client() -> TestClient:
    return _client(_FakeApi())


def _json_ld(html: str) -> dict[str, object]:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert match is not None, "no se encontró JSON-LD"
    return json.loads(match.group(1))


def test_obra_sin_slug_redirige_al_canonico(client: TestClient) -> None:
    resp = client.get("/obra/index-7", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/obra/index-7/ave-verum-corpus"


def test_obra_slug_incorrecto_redirige_al_canonico(client: TestClient) -> None:
    resp = client.get("/obra/index-7/cualquier-cosa", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/obra/index-7/ave-verum-corpus"


def test_pagina_de_obra_tiene_html_real_y_metadatos(client: TestClient) -> None:
    resp = client.get("/obra/index-7/ave-verum-corpus")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<h1>Ave verum corpus</h1>" in resp.text
    assert (
        f'<link rel="canonical" href="{_BASE}/obra/index-7/ave-verum-corpus" />'
        in resp.text
    )
    assert "Wolfgang Amadeus Mozart" in resp.text
    assert 'href="/compositor/person-1/wolfgang-amadeus-mozart"' in resp.text
    assert "KV 618" in resp.text
    # Recursos enlazados.
    assert "https://storage.openmusicrepository.com/api/download/9" in resp.text
    assert "https://imslp.org/wiki/Ave_verum" in resp.text


def test_pagina_de_obra_json_ld_es_music_composition(client: TestClient) -> None:
    payload = _json_ld(
        client.get("/obra/index-7/ave-verum-corpus").text
    )
    graph = payload["@graph"]
    assert isinstance(graph, list)
    composition = next(node for node in graph if node["@type"] == "MusicComposition")
    assert composition["name"] == "Ave verum corpus"
    assert composition["composer"]["name"] == "Wolfgang Amadeus Mozart"
    assert composition["identifier"] == "KV 618"
    crumbs = next(node for node in graph if node["@type"] == "BreadcrumbList")
    assert len(crumbs["itemListElement"]) == 4


def test_obra_desconocida_404_html(client: TestClient) -> None:
    resp = client.get("/obra/index-999/lo-que-sea")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")
    assert "No encontrado" in resp.text
    assert "NOT_FOUND" not in resp.text
    # Un 404 nunca debe invitar a indexar ni declarar canonical.
    assert 'name="robots" content="noindex, nofollow"' in resp.text
    assert 'rel="canonical"' not in resp.text


def test_titulo_con_script_no_rompe_json_ld() -> None:
    malicious = dict(_WORK)
    malicious["title"] = "Ave </script><script>alert(1)</script>"
    client = _client(_FakeApi(work=malicious))
    html = client.get("/obra/index-7", follow_redirects=True).text
    assert "</script><script>alert(1)" not in html
    assert "\\u003c/script\\u003e" in html
    payload = _json_ld(html)
    composition = next(node for node in payload["@graph"] if node["@type"] == "MusicComposition")
    assert composition["name"] == "Ave </script><script>alert(1)</script>"


def test_obra_sin_compositor_ni_recursos_genera_html_valido() -> None:
    lonely = {
        "work_id": "index-9",
        "title": "Anónimo",
        "composer": None,
        "composer_id": None,
        "catalogue": None,
        "year": None,
        "instrumentation": None,
        "representations": [],
    }
    client = _client(_FakeApi(work=lonely, works={"items": [], "total": 0}))
    resp = client.get("/obra/index-9/anonimo")
    assert resp.status_code == 200
    assert "<h1>Anónimo</h1>" in resp.text
    assert "compositor desconocido" in resp.text
    assert "Todavía no hay recursos" in resp.text
    assert 'href="/compositor/' not in resp.text


def test_titulos_unicode_y_acentos_no_rompen_el_html() -> None:
    unicode_work = dict(_WORK)
    unicode_work["title"] = "Cántico de la Résurrection — Œuvre"
    unicode_work["composer"] = "José Pérez"
    client = _client(_FakeApi(work=unicode_work))
    resp = client.get("/obra/index-7", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/obra/index-7/cantico-de-la-resurrection-oeuvre"
    page = client.get(resp.headers["location"]).text
    assert "Cántico de la Résurrection — Œuvre" in page
    assert "José Pérez" in page


def test_compositor_sin_slug_redirige_al_canonico(client: TestClient) -> None:
    resp = client.get("/compositor/person-1", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/compositor/person-1/wolfgang-amadeus-mozart"


def test_pagina_de_compositor_lista_obras_y_json_ld(client: TestClient) -> None:
    resp = client.get("/compositor/person-1/wolfgang-amadeus-mozart")
    assert resp.status_code == 200
    assert "<h1>Wolfgang Amadeus Mozart</h1>" in resp.text
    assert 'href="/obra/index-7/ave-verum-corpus"' in resp.text
    assert 'href="/obra/index-8/requiem"' in resp.text
    assert f'<link rel="canonical" href="{_BASE}/compositor/person-1/wolfgang-amadeus-mozart" />' in resp.text
    payload = _json_ld(resp.text)
    graph = payload["@graph"]
    person = next(node for node in graph if node["@type"] == "Person")
    assert person["name"] == "Wolfgang Amadeus Mozart"
    assert person["birthDate"] == "1756"
    assert person["deathDate"] == "1791"


def test_compositor_desconocido_404_html(client: TestClient) -> None:
    resp = client.get("/compositor/nadie/quien-sea")
    assert resp.status_code == 404
    assert "No encontrado" in resp.text
