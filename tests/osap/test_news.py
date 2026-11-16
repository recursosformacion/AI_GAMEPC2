"""Noticias: cliente interno y contrato de la API de OSAP."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.osap.api import platform_app
from src.osap.api.platform import PlatformApi
from src.osap.infrastructure.news.client import NewsClient, NewsUnavailableError


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_news_client_sends_language_and_topics(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["token"] = request.headers.get("X-osap-news-token")
        return _Response({"items": [{"title": "Ave verum"}], "count": 1})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = NewsClient(base_url="http://news.test", token="secret", timeout=4.0)

    data = client.query(languages=["ca"], topics=["coral", "clàssica"], limit=5, days=90)

    assert data["count"] == 1
    assert captured["timeout"] == 4.0
    assert captured["token"] == "secret"
    assert captured["url"].startswith("http://news.test/api/v1/news?")
    assert "languages=ca" in captured["url"]
    assert "topics=coral%2Ccl%C3%A0ssica" in captured["url"]
    assert "limit=5" in captured["url"]
    assert "days=90" in captured["url"]


def test_news_client_fails_closed_without_token() -> None:
    client = NewsClient(base_url="http://news.test", token=None)
    with pytest.raises(NewsUnavailableError):
        client.topics()


def test_api_news_uses_the_authenticated_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_feed(self: PlatformApi, token: str | None, **kwargs: Any) -> dict[str, object]:
        assert token == "Bearer user-token"
        assert kwargs["limit"] == 3
        return {
            "items": [{"title": "Noticia"}],
            "language": "es",
            "topics": ["coral"],
            "opt_in": False,
            "personalized": True,
            "window_days": 30,
        }

    monkeypatch.setattr(PlatformApi, "news_feed", fake_feed)
    with TestClient(platform_app.create_platform_app()) as client:
        response = client.get(
            "/api/v1/news?limit=3",
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["title"] == "Noticia"


def test_api_news_maps_unavailable_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(self: PlatformApi, token: str | None, **kwargs: Any) -> dict[str, object]:
        raise NewsUnavailableError("down")

    monkeypatch.setattr(PlatformApi, "news_feed", unavailable)
    with TestClient(platform_app.create_platform_app()) as client:
        response = client.get("/api/v1/news")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NEWS_UNAVAILABLE"

