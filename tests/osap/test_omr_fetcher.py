"""OmrStorageFetcher: contrato con el Provider API de storage (v1.3)."""

import json

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery
from src.osap.infrastructure.providers.fetchers import omr_fetcher
from src.osap.infrastructure.providers.fetchers.omr_fetcher import OmrStorageFetcher, _remote_id

PAYLOAD = {
    "works": [
        {
            "id": 101,
            "title": "Downloadable",
            "composer": "X",
            "resources": [
                {"id": "281", "available": True, "links": {"download": "/api/download/281"}}
            ],
        },
        {"id": 102, "title": "CPDL inventory", "composer": None, "resources": []},
        {
            "id": 103,
            "title": "Unavailable",
            "resources": [
                {"id": "x", "available": False, "links": {"download": None}}
            ],
        },
    ]
}


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _patch_urlopen(monkeypatch, payload: dict) -> None:
    def fake_urlopen(request, timeout=None):  # noqa: ANN001, ARG001
        return _FakeResponse(payload)

    monkeypatch.setattr(omr_fetcher.urllib.request, "urlopen", fake_urlopen)


def test_fetch_keeps_identified_works_without_resource(monkeypatch) -> None:
    # CPDL está identificado en `works` aunque aún no tenga recurso: no se descarta.
    _patch_urlopen(monkeypatch, PAYLOAD)
    fetcher = OmrStorageFetcher(base_url="http://storage.test")
    works = fetcher.fetch(None, None, ProviderQuery(composer="X"))["works"]
    assert [w["id"] for w in works] == ["101", "102", "103"]

    downloadable = next(w for w in works if w["id"] == "101")
    assert downloadable["resources"][0]["links"]["download"] == (
        "http://storage.test/api/download/281"
    )

    inventory = next(w for w in works if w["id"] == "102")
    assert inventory["resources"] == []
    assert inventory["title"] == "CPDL inventory"


def test_remote_id_uses_contract_id_not_file_id() -> None:
    assert _remote_id({"id": 101}) == "101"
    assert _remote_id({"id": 7}) == "7"
    assert _remote_id({"id": 101}) != _remote_id({"id": 102})
    # sin id, cae a file_id/relative_path (compatibilidad)
    assert _remote_id({"file_id": 9}) == "9"


def test_empty_query_returns_empty_without_network() -> None:
    fetcher = OmrStorageFetcher(base_url="http://storage.test")
    assert fetcher.fetch(None, None, ProviderQuery(query="")) == {"works": []}
