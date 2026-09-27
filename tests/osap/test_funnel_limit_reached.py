"""Paso 3 (4.2): el 429 real emite `limit_reached` de forma observacional.

Invariantes comprobadas:
- el 429 lo produce el circuito de cuota actual y se devuelve intacto;
- se registra UN evento `limit_reached` con stage S1 (anónimo) o S3 (usuario);
- el quota store no recibe escrituras adicionales por el 429 (ni contador ni usage);
- si el funnel falla, el 429 sigue devolviéndose.
"""

from __future__ import annotations

import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.http import search as search_http
from src.osap.api.http.context import HttpContext
from src.osap.api.http.search import build_search_router
from src.osap.api.platform.analytics import AnalyticsMixin
from src.osap.api.platform.funnel import FunnelMixin
from src.osap.api.platform.quota import QuotaMixin
from src.osap.infrastructure.state.analytics.memory import MemoryStore as AnalyticsMem
from src.osap.infrastructure.state.analytics.recorder import AnalyticsRecorder
from src.osap.infrastructure.state.funnel.memory import FunnelEvent
from src.osap.infrastructure.state.funnel.memory import MemoryStore as FunnelStore
from src.osap.infrastructure.state.quota.memory import MemoryStore as QuotaStore
from src.osap.infrastructure.state.quota.memory import today

OMR_REP = "idx-42-omr-musicxml"
URL = f"/api/v1/representations/{OMR_REP}/download"


class _Upstream:
    status_code = 200
    content = b"MXL-DATA"
    headers = {"content-type": "application/vnd.recordare.musicxml"}


class _FakeContainer:
    def storage_web_base(self) -> str:
        return "https://storage.openmusicrepository.com"


class _BrokenFunnel:
    def record_event(self, *a: object, **k: object) -> object:
        raise RuntimeError("funnel caido")


class _Api(AnalyticsMixin, QuotaMixin, FunnelMixin):
    """API mínima con cuota + analítica + funnel para ejercer la ruta de descarga."""

    def __init__(self, *, user_id: str | None = None, funnel: object | None = None) -> None:
        self._analytics = AnalyticsRecorder(AnalyticsMem())
        self._quota_store = QuotaStore()
        self._funnel_store = funnel if funnel is not None else FunnelStore()
        self._user_id = user_id
        self._info: dict[str, object] = {
            "download_url": "https://storage.openmusicrepository.com/api/download/x.mxl",
            "provider": "omr",
            "work_id": "42",
            "format": "musicxml",
        }

    def get_representation_download(self, representation_id: str) -> dict[str, object]:
        return dict(self._info)

    def current_user(self, token: str | None) -> object:
        if self._user_id:
            return types.SimpleNamespace(user_id=self._user_id, roles=("user",))
        raise RuntimeError("auth down")


def _client(api: _Api, monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(build_search_router(HttpContext(api=api, container=_FakeContainer())))  # type: ignore[arg-type]
    monkeypatch.setattr(search_http.requests, "get", lambda *a, **k: _Upstream())
    return TestClient(app)


def _hit(client: TestClient, n: int) -> list[int]:
    return [client.get(URL).status_code for _ in range(n)]


def test_anonimo_emite_stage_s1_y_no_escribe_cuota(monkeypatch) -> None:
    api = _Api()
    client = _client(api, monkeypatch)
    codes = _hit(client, 11)
    assert codes[:10] == [200] * 10
    assert codes[10] == 429

    funnel = api._funnel_store
    assert funnel.count() == 1  # un único evento por el 429
    ev = funnel.events[0]
    assert ev["event"] == FunnelEvent.LIMIT_REACHED.value
    assert ev["stage"] == "S1"
    assert ev["user_id"] is None
    assert ev["ip_address"] == "testclient"

    # Cuota intacta: contador = límite y ninguna fila de uso por el intento denegado.
    quota = api._quota_store
    assert quota._used(today(), "ip:testclient") == 10
    assert len(quota.usage) == 10


def test_usuario_emite_stage_s3_y_429_intacto(monkeypatch) -> None:
    api = _Api(user_id="u1")
    client = _client(api, monkeypatch)
    codes = _hit(client, 101)
    assert codes[:100] == [200] * 100
    assert codes[100] == 429

    funnel = api._funnel_store
    assert funnel.count() == 1
    ev = funnel.events[0]
    assert ev["stage"] == "S3"
    assert ev["user_id"] == "u1"

    quota = api._quota_store
    assert quota._used(today(), "u:u1") == 100
    assert len(quota.usage) == 100


def test_respuesta_429_intacta(monkeypatch) -> None:
    api = _Api()
    client = _client(api, monkeypatch)
    _hit(client, 10)
    resp = client.get(URL)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_fallo_del_funnel_no_cambia_el_429(monkeypatch) -> None:
    api = _Api(funnel=_BrokenFunnel())
    client = _client(api, monkeypatch)
    codes = _hit(client, 11)
    assert codes[:10] == [200] * 10
    assert codes[10] == 429  # el fallo del funnel se traga; la respuesta no cambia
