"""V1 — Tests del fetcher de MusicBrainz."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery
from src.osap.infrastructure.providers.fetchers.musicbrainz_fetcher import MusicBrainzFetcher

_PAYLOAD = {
    "works": [
        {
            "id": "d63c68b1-1ec1-38b7-aee9-c52b9b47c80f",
            "title": "Ave verum corpus, K. 618",
            "type": "Motet",
            "relations": [
                {
                    "type": "composer",
                    "direction": "backward",
                    "artist": {"id": "b972f589-fb0e-474e-b64a-803b0364fa75", "name": "Wolfgang Amadeus Mozart"},
                }
            ],
        }
    ]
}


class _FakeResponse:
    status = 200

    def read(self) -> bytes:
        return json.dumps(_PAYLOAD).encode()

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _query(composer: str | None = None, title: str | None = None, text: str = "") -> ProviderQuery:
    return ProviderQuery(query=text, composer=composer, title=title, limit=50)


def test_musicbrainz_fetcher_normalizes_works() -> None:
    captured: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: int = 15) -> _FakeResponse:  # noqa: ARG001
        captured.append(request)
        return _FakeResponse()

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen  # type: ignore[assignment]
    try:
        result = MusicBrainzFetcher().fetch(None, None, _query(composer="Mozart", title="Ave Verum"))
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]

    assert captured, "se esperaba una llamada a MusicBrainz"
    url = urllib.parse.unquote(captured[0].full_url)
    assert 'artist:"Mozart"' in url
    assert 'work:"Ave Verum"' in url
    works = result["works"]
    assert isinstance(works, list) and len(works) == 1
    work = works[0]
    assert "Ave verum" in work["title"]
    assert work["composer"] == "Wolfgang Amadeus Mozart"
    res = work["resources"][0]
    # Se entrega el enlace (página + API JSON); MusicBrainz no tiene fichero.
    assert res["format"] == "json"
    assert res["view_url"] == "https://musicbrainz.org/work/d63c68b1-1ec1-38b7-aee9-c52b9b47c80f"


def test_musicbrainz_empty_without_query() -> None:
    assert MusicBrainzFetcher().fetch(None, None, _query()) == {"works": []}
