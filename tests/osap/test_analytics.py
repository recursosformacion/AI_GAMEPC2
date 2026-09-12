"""Tests de la analítica de uso (F-A): store, recorder, mixin y MySQL.

Incluye la propiedad arquitectónica clave: **un fallo del recorder/store nunca altera la
respuesta** de una búsqueda ni de una descarga (la analítica es observación, no camino
crítico).
"""

import pymysql
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.contracts import SearchRequest, SearchResponse
from src.osap.api.http import search as search_http
from src.osap.api.http.context import HttpContext
from src.osap.api.http.search import build_search_router
from src.osap.api.platform import PlatformApi
from src.osap.api.platform._support import _search_signature
from src.osap.api.platform.analytics import AnalyticsMixin
from src.osap.infrastructure.state.analytics.memory import MemoryStore, today
from src.osap.infrastructure.state.analytics.recorder import AnalyticsRecorder
from src.osap.infrastructure.state.analytics_store import build_analytics_store

DAY = "2026-09-12"
TEST_DB = "osap_api_test"


def test_search_counters_and_overview() -> None:
    store = MemoryStore()
    store.record_search(DAY, 3)
    store.record_search(DAY, 0)
    store.record_search_batch(DAY, 5, 4, 1)
    overview = store.usage_overview(DAY, DAY)
    assert overview["searches_total"] == 7
    assert overview["searches_with_results"] == 5
    assert overview["searches_without_results"] == 2


def test_downloads_dimension_and_overview() -> None:
    store = MemoryStore()
    store.record_download(DAY, "u1", "omr", "42", "musicxml", bytes_transferred=100)
    store.record_download(DAY, "u1", "omr", "42", "musicxml", bytes_transferred=50)
    store.record_download(DAY, "u2", "imslp", "7", "pdf")
    store.record_download_failure(DAY, "imslp")
    overview = store.usage_overview(DAY, DAY)
    assert overview["downloads_total"] == 3
    assert overview["downloads_bytes"] == 150
    assert overview["downloads_users"] == 2


def test_overview_filters_by_day() -> None:
    store = MemoryStore()
    store.record_search("2026-09-01", 1)
    store.record_search(DAY, 1)
    assert store.usage_overview(DAY, DAY)["searches_total"] == 1


def test_recorder_aggregates_and_flushes() -> None:
    store = MemoryStore()
    recorder = AnalyticsRecorder(store, flush_interval=3600)
    recorder.record_search(2)
    recorder.record_search(0)
    recorder.record_download("omr", "1", "pdf", user_id="u1", bytes_transferred=10)
    recorder.record_download("omr", "1", "pdf", user_id="u1", bytes_transferred=5)
    recorder.record_download_failure("imslp")
    recorder.flush()
    day = today()
    overview = store.usage_overview(day, day)
    assert overview["searches_total"] == 2
    assert overview["searches_with_results"] == 1
    assert overview["searches_without_results"] == 1
    assert overview["downloads_total"] == 2
    assert overview["downloads_bytes"] == 15
    assert overview["downloads_users"] == 1


class _BoomStore(MemoryStore):
    def record_search_batch(self, day: str, total: int, with_results: int, without_results: int) -> None:
        raise RuntimeError("boom")


def test_recorder_never_raises_on_store_failure() -> None:
    recorder = AnalyticsRecorder(_BoomStore(), flush_interval=3600)
    recorder.record_search(1)
    recorder.flush()


class _StubApi(AnalyticsMixin):
    def __init__(self, store: MemoryStore, recorder: AnalyticsRecorder) -> None:
        self._analytics_store = store
        self._analytics = recorder


def test_mixin_records_and_reads() -> None:
    store = MemoryStore()
    recorder = AnalyticsRecorder(store, flush_interval=3600)
    api = _StubApi(store, recorder)
    api.record_search_event(1)
    api.record_download_event(provider="omr", work_id="1", fmt="pdf", user_id="u1", bytes_transferred=4)
    api.record_download_failure_event(provider="imslp")
    overview = api.analytics_overview(today(), today())
    assert overview["searches_total"] == 1
    assert overview["searches_with_results"] == 1
    assert overview["downloads_total"] == 1
    assert overview["downloads_bytes"] == 4


def test_mysql_store_roundtrip() -> None:
    try:
        base = pymysql.connect(
            host="127.0.0.1", user="osap2027", password="2027osapdb", charset="utf8mb4", autocommit=True
        )
    except pymysql.err.OperationalError:
        pytest.skip("MySQL local no disponible")
    with base.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {TEST_DB}")
    base.close()

    store = build_analytics_store(database=TEST_DB)
    if not hasattr(store, "_run"):
        pytest.skip("El store de analítica degradó a memoria (MySQL no disponible)")
    conn = pymysql.connect(
        host="127.0.0.1",
        user="osap2027",
        password="2027osapdb",
        database=TEST_DB,
        charset="utf8mb4",
        autocommit=True,
    )
    with conn.cursor() as cur:
        for table in ("analytics_search_daily", "analytics_downloads", "analytics_provider_daily"):
            cur.execute(f"DELETE FROM {table}")
    conn.close()

    store.record_search(DAY, 2)
    store.record_search(DAY, 0)
    store.record_download(DAY, "u1", "omr", "1", "pdf", bytes_transferred=30)
    store.record_download_failure(DAY, "omr")

    overview = store.usage_overview(DAY, DAY)
    assert overview["searches_total"] == 2
    assert overview["searches_with_results"] == 1
    assert overview["searches_without_results"] == 1
    assert overview["downloads_total"] == 1
    assert overview["downloads_bytes"] == 30
    assert overview["downloads_users"] == 1

    rows = store._run(  # type: ignore[attr-defined]
        "SELECT downloads, downloads_failed, bytes FROM analytics_provider_daily "
        "WHERE day = %s AND provider = %s",
        (DAY, "omr"),
    )
    assert rows and rows[0]["downloads"] == 1
    assert rows[0]["downloads_failed"] == 1
    assert rows[0]["bytes"] == 30


# --- propiedad: la analítica no altera la respuesta -------------------------


class _ExplodingAnalytics:
    """Simula un recorder/store caído: toda llamada lanza."""

    def record_search(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("analytics down")

    def record_download(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("analytics down")

    def record_download_failure(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("analytics down")

    def flush(self) -> None:
        raise RuntimeError("analytics down")


def test_mixin_never_propagates_analytics_failure() -> None:
    api = _StubApi(MemoryStore(), _ExplodingAnalytics())  # type: ignore[arg-type]
    api.record_search_event(1)
    api.record_download_event(provider="omr", work_id="1", fmt="pdf", user_id="u1")
    api.record_download_failure_event(provider="imslp")


def test_search_response_unaffected_when_analytics_explodes() -> None:
    api = PlatformApi.__new__(PlatformApi)
    api._searches = {}
    api._search_cache = {}
    api._analytics = _ExplodingAnalytics()  # type: ignore[assignment]
    api._analytics_store = MemoryStore()
    request = SearchRequest(query="ave verum")
    api._search_cache[_search_signature(request)] = SearchResponse(
        search_id="cached", total=1, results=[], page=1, per_page=10, status="done", progress=100
    )
    search_id, response = api.create_search(request)
    assert search_id
    assert response.status == "done"
    assert response.total == 1


class _FakeUpstream:
    status_code = 200
    content = b"MXL-DATA"
    headers = {"content-type": "application/vnd.recordare.musicxml"}


class _FakeContainer:
    def storage_web_base(self) -> str:
        return "https://cdn.openmusicrepository.com"


class _DownloadApi(AnalyticsMixin):
    """API mínima con los métodos que usa la ruta de descarga."""

    def __init__(self, analytics: object) -> None:
        self._analytics = analytics
        self._info: dict[str, object] = {
            "download_url": "https://cdn.openmusicrepository.com/api/download/x.mxl",
            "provider": "omr",
            "work_id": "42",
            "format": "musicxml",
        }

    def get_representation_download(self, representation_id: str) -> dict[str, object]:
        return dict(self._info)

    def current_user(self, token: str | None) -> object:
        # Sin auth disponible: no puede impedir la descarga (ni la analítica).
        raise RuntimeError("auth down")


def _download_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    api = _DownloadApi(_ExplodingAnalytics())
    app = FastAPI()
    app.include_router(build_search_router(HttpContext(api=api, container=_FakeContainer())))  # type: ignore[arg-type]
    monkeypatch.setattr(search_http.requests, "get", lambda *args, **kwargs: _FakeUpstream())
    return TestClient(app)


def test_download_response_unaffected_when_analytics_explodes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _download_client(monkeypatch)
    response = client.get("/api/v1/representations/idx-42-omr-musicxml/download")
    assert response.status_code == 200
    assert response.content == b"MXL-DATA"


def test_download_failure_response_unaffected_when_analytics_explodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenUpstream:
        status_code = 500
        content = b""
        headers: dict[str, str] = {}

    client = _download_client(monkeypatch)
    monkeypatch.setattr(search_http.requests, "get", lambda *args, **kwargs: _BrokenUpstream())
    response = client.get("/api/v1/representations/idx-42-omr-musicxml/download")
    assert response.status_code == 502
