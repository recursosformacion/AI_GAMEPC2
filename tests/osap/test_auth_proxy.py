"""V1 — Tests del proxy de registro/verificación (osap-api → osap-auth)."""

from __future__ import annotations

import json
import urllib.request

from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
from src.osap.bootstrap.container import Container
from src.osap.infrastructure.auth.auth_proxy_client import AuthProxyClient


class _FakeResponse:
    status = 200

    def __init__(self, body: bytes = b"{}", status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _build(handler) -> TestClient:
    container = Container()
    container.set_auth_proxy(AuthProxyClient(base_url="http://127.0.0.1:1"))
    return TestClient(create_platform_app(container=container))


def test_register_proxies_to_osap_auth_and_relays() -> None:
    captured: list[urllib.request.Request] = []

    def fake(request: urllib.request.Request, timeout: int = 15) -> _FakeResponse:  # noqa: ARG001
        captured.append(request)
        return _FakeResponse(json.dumps({"user_id": "u1", "verification_token": None, "message": "ok"}).encode())

    original = urllib.request.urlopen
    urllib.request.urlopen = fake  # type: ignore[assignment]
    try:
        client = _build(fake)
        resp = client.post("/api/v1/auth/register", json={"email": "a@b.c", "password": "password123", "name": "A"})
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user_id"] == "u1"
    body = json.loads(captured[0].data.decode())
    assert body["email"] == "a@b.c"
    assert body["password"] == "password123"


def test_register_email_exists_returns_generic_200() -> None:
    # Anti-enumeración: email existente → misma respuesta genérica (user_id null), no 409.
    def fake(request: urllib.request.Request, timeout: int = 15) -> _FakeResponse:  # noqa: ARG001
        return _FakeResponse(json.dumps({"user_id": None, "verification_token": None, "message": "generic"}).encode())

    original = urllib.request.urlopen
    urllib.request.urlopen = fake  # type: ignore[assignment]
    try:
        client = _build(fake)
        resp = client.post("/api/v1/auth/register", json={"email": "a@b.c", "password": "password123"})
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]
    assert resp.status_code == 200
    assert resp.json()["data"]["user_id"] is None


def test_register_422_relayed() -> None:
    class _Err(_FakeResponse):
        status = 422

    def fake(request: urllib.request.Request, timeout: int = 15) -> _FakeResponse:  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 422, "Validation Error", {}, None)

    original = urllib.request.urlopen
    urllib.request.urlopen = fake  # type: ignore[assignment]
    try:
        client = _build(fake)
        resp = client.post("/api/v1/auth/register", json={"email": "a@b.c", "password": "short"})
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]
    assert resp.status_code == 422


def test_verify_email_proxies_and_relays() -> None:
    captured: list[urllib.request.Request] = []

    def fake(request: urllib.request.Request, timeout: int = 15) -> _FakeResponse:  # noqa: ARG001
        captured.append(request)
        return _FakeResponse(json.dumps({"message": "email verificado"}).encode())

    original = urllib.request.urlopen
    urllib.request.urlopen = fake  # type: ignore[assignment]
    try:
        client = _build(fake)
        resp = client.post("/api/v1/auth/verify-email", json={"token": "tok"})
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]

    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "email verificado"
    assert captured[0].full_url.endswith("/auth/verify-email")
