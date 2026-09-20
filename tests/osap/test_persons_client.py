"""Tests del puente `persons` (nuevo) / `composers` (v1) del cliente de osap-storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.infrastructure.storage.storage_composer_client import StorageComposerClient

if TYPE_CHECKING:
    import pytest


def _client() -> StorageComposerClient:
    return StorageComposerClient(base_url="http://storage.test", timeout=5)


def test_list_persons_usa_persons_y_anota_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    calls: list[str] = []

    def fake_perform(method: str, path: str, payload: object, scope: str, provider: object):
        calls.append(path)
        if path.startswith("/api/admin/persons?"):
            return 200, {"items": [{"id": "p1", "name": "Ada", "role_ids": [1, 3]}], "total": 1}
        return 404, {}

    monkeypatch.setattr(client, "_perform", fake_perform)
    data = client.list_persons(("composer", "arranger"), None, 10, 0)

    assert calls[0].startswith("/api/admin/persons?role=composer%2Carranger")
    assert data["total"] == 1
    assert data["items"][0]["roles"] == ["composer", "arranger"]


def test_list_persons_cae_a_composers_si_no_hay_persons(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    calls: list[str] = []

    def fake_perform(method: str, path: str, payload: object, scope: str, provider: object):
        calls.append(path)
        if path.startswith("/api/admin/composers?"):
            return 200, {"items": [{"id": "p2", "name": "Bach"}], "total": 1}
        return 404, {}

    monkeypatch.setattr(client, "_perform", fake_perform)
    data = client.list_persons(("composer",), None, 10, 0)

    assert any(path.startswith("/api/admin/persons?") for path in calls)
    assert any(path.startswith("/api/admin/composers?") for path in calls)
    assert data["items"][0]["id"] == "p2"
    # Sin `role_ids` el item queda sin roles explícitos (la v1 solo conoce compositores).
    assert data["items"][0]["roles"] == []


def test_call_reintenta_con_persons_si_composers_desaparece(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    calls: list[str] = []

    def fake_perform(method: str, path: str, payload: object, scope: str, provider: object):
        calls.append(path)
        if "/persons" in path:
            return 200, {"id": "p1", "name": "Ada"}
        return 404, {}

    monkeypatch.setattr(client, "_perform", fake_perform)
    status, doc = client._call("GET", "/api/admin/composers/p1")

    assert status == 200
    assert calls == ["/api/admin/composers/p1", "/api/admin/persons/p1"]
    assert doc == {"id": "p1", "name": "Ada"}
