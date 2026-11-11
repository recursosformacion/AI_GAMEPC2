"""V1 — Fachada del espacio de trabajo (osap-api → Chorus)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
from src.osap.bootstrap.container import Container


class _Upstream:
    def __init__(self, status_code: int = 200, payload: object | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _client(base: str | None = "http://chorus.test") -> TestClient:
    container = Container()
    container.set_chorus_config(base)
    return TestClient(create_platform_app(container=container))


def test_library_forwards_session_and_query(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake(method: str, url: str, **kwargs: object) -> _Upstream:
        captured.update({"method": method, "url": url, **kwargs})
        return _Upstream(200, {"items": [], "collections": []})

    monkeypatch.setattr("src.osap.api.http.workspace.requests.request", fake)
    response = _client().get(
        "/api/v1/workspace/library",
        params={"q": "ave"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"items": [], "collections": []}}
    assert captured["method"] == "GET"
    assert captured["url"] == "http://chorus.test/api/v1/library"
    assert captured["params"] == {"q": "ave"}
    assert captured["headers"] == {"Authorization": "Bearer token"}


def test_save_reference_relays_created_and_body(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake(method: str, url: str, **kwargs: object) -> _Upstream:
        captured.update({"method": method, "url": url, **kwargs})
        return _Upstream(201, {"id": "item-1", "title": "Ave verum"})

    monkeypatch.setattr("src.osap.api.http.workspace.requests.request", fake)
    response = _client().post(
        "/api/v1/workspace/library",
        json={
            "provider": "cpdl",
            "work_id": "index-1",
            "representation_id": "idx-1-cpdl-2-musicxml",
            "title": "Ave verum",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["id"] == "item-1"
    assert captured["url"] == "http://chorus.test/api/v1/library/references"
    assert captured["json"] == {
        "provider": "cpdl",
        "work_id": "index-1",
        "representation_id": "idx-1-cpdl-2-musicxml",
        "title": "Ave verum",
    }


def test_workspace_requires_session(monkeypatch) -> None:
    def fake(*args: object, **kwargs: object) -> _Upstream:  # noqa: ARG001
        raise AssertionError("no debe llamarse sin sesión")

    monkeypatch.setattr("src.osap.api.http.workspace.requests.request", fake)
    response = _client().get("/api/v1/workspace/library")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_workspace_without_chorus_base_is_503() -> None:
    response = _client(None).get(
        "/api/v1/workspace/library", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "WORKSPACE_UNAVAILABLE"
