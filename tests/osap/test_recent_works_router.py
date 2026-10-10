"""Tests del endpoint de novedades de portada (/api/v1/works/recent)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.http.context import HttpContext
from src.osap.api.http.works import build_works_router

_ITEMS = [
    {
        "work_id": "index-9",
        "title": "Ave verum corpus",
        "composer": "Wolfgang Amadeus Mozart",
        "path": "/obra/index-9/ave-verum-corpus",
    },
    {"work_id": "index-8", "title": "Réquiem", "composer": None, "path": "/obra/index-8/requiem"},
]


class _FakeApi:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self._items = items

    def recent_works(self, limit: int) -> list[dict[str, object]]:
        return self._items[:limit]


def _client(items: list[dict[str, object]]) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_works_router(HttpContext(api=_FakeApi(items), container=object()))  # type: ignore[arg-type]
    )
    return TestClient(app)


@pytest.fixture()
def client() -> TestClient:
    return _client(_ITEMS)


def test_recent_works_devuelve_items_con_path(client: TestClient) -> None:
    resp = client.get("/api/v1/works/recent", params={"limit": 2})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert [i["work_id"] for i in items] == ["index-9", "index-8"]
    assert items[0]["path"] == "/obra/index-9/ave-verum-corpus"


def test_recent_works_acota_el_limite_a_24() -> None:
    many = [{"work_id": f"index-{n}", "title": "Obra", "path": f"/obra/index-{n}/obra"} for n in range(30)]
    resp = _client(many).get("/api/v1/works/recent", params={"limit": 100})
    assert resp.status_code == 200
    assert len(resp.json()["data"]["items"]) == 24
