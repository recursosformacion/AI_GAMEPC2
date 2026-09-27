"""Paso 4 (4.2): `registered`/S2 tras un registro confirmado, sin tocar auth.

Invariantes:
- el evento solo se emite si osap-auth confirma el registro (hay `user_id`);
- `stage=S2` y `user_id` obligatorio;
- registro fallido → ningún `registered`;
- fallo del funnel → el registro sigue siendo exitoso;
- idempotencia: reintentos de la misma operación no duplican el evento.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.http.auth import build_auth_router
from src.osap.api.http.context import HttpContext
from src.osap.api.platform.funnel import FunnelMixin
from src.osap.infrastructure.state.funnel.memory import FunnelEvent
from src.osap.infrastructure.state.funnel.memory import MemoryStore as FunnelStore

PAYLOAD = {"email": "nuevo@example.invalid", "password": "Contraseña-2026", "name": "Nuevo"}


class _BrokenFunnel:
    def has_event(self, *a: object, **k: object) -> bool:
        raise RuntimeError("funnel caido")

    def record_event(self, *a: object, **k: object) -> object:
        raise RuntimeError("funnel caido")


class _Api(FunnelMixin):
    def __init__(self, *, result: tuple[int, dict[str, object]], funnel: object | None = None) -> None:
        self._funnel_store = funnel if funnel is not None else FunnelStore()
        self._result = result

    def register_user(
        self, email: str, password: str, name: str | None = None
    ) -> tuple[int, dict[str, object]]:
        return self._result


def _client(api: _Api) -> TestClient:
    app = FastAPI()
    app.include_router(build_auth_router(HttpContext(api=api, container=object())))  # type: ignore[arg-type]
    return TestClient(app)


def test_registro_valido_emite_registered_s2() -> None:
    api = _Api(result=(200, {"user_id": "u-1", "message": "ok"}))
    resp = _client(api).post("/api/v1/auth/register", json=PAYLOAD)
    assert resp.status_code == 200

    funnel = api._funnel_store
    assert funnel.count() == 1
    ev = funnel.events[0]
    assert ev["event"] == FunnelEvent.REGISTERED.value
    assert ev["stage"] == "S2"
    assert ev["user_id"] == "u-1"
    assert ev["ip_address"] == "testclient"


def test_registro_fallido_no_emite_evento() -> None:
    api = _Api(result=(422, {"detail": "invalid"}))
    resp = _client(api).post("/api/v1/auth/register", json=PAYLOAD)
    assert resp.status_code == 422
    assert api._funnel_store.count() == 0

    api2 = _Api(result=(503, {"detail": "down"}))
    assert _client(api2).post("/api/v1/auth/register", json=PAYLOAD).status_code == 502
    assert api2._funnel_store.count() == 0


def test_sin_user_id_no_emite_evento() -> None:
    # Anti-enumeración: respuesta genérica sin user_id → no hay confirmación de alta.
    api = _Api(result=(200, {"message": "Si el email es nuevo…"}))
    assert _client(api).post("/api/v1/auth/register", json=PAYLOAD).status_code == 200
    assert api._funnel_store.count() == 0


def test_fallo_del_funnel_no_rompe_el_registro() -> None:
    api = _Api(result=(200, {"user_id": "u-2"}))
    api._funnel_store = _BrokenFunnel()
    assert _client(api).post("/api/v1/auth/register", json=PAYLOAD).status_code == 200


def test_reintento_no_duplica_registered() -> None:
    api = _Api(result=(200, {"user_id": "u-3"}))
    client = _client(api)
    client.post("/api/v1/auth/register", json=PAYLOAD)
    client.post("/api/v1/auth/register", json=PAYLOAD)  # reintento
    assert api._funnel_store.count(FunnelEvent.REGISTERED) == 1
