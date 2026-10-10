"""Tests del transporte IndexNow (payload, lotes, host y URL de la clave)."""

from __future__ import annotations

from src.osap.api.seo.indexnow import (
    chunked,
    indexnow_host,
    indexnow_key_location,
    indexnow_payload,
)


def test_host_y_key_location() -> None:
    assert indexnow_host("https://app.openmusicrepository.com") == "app.openmusicrepository.com"
    assert indexnow_host("https://app.openmusicrepository.com/") == "app.openmusicrepository.com"
    assert (
        indexnow_key_location("https://app.openmusicrepository.com/", "osap-indexnow-2026")
        == "https://app.openmusicrepository.com/osap-indexnow-2026.txt"
    )


def test_payload_incluye_host_clave_y_urls() -> None:
    payload = indexnow_payload("h", "k", "https://h/k.txt", ["https://h/obra/index-1/x"])
    assert payload == {
        "host": "h",
        "key": "k",
        "keyLocation": "https://h/k.txt",
        "urlList": ["https://h/obra/index-1/x"],
    }


def test_chunked_respeta_tamano_y_ultimo_lote() -> None:
    assert list(chunked([], 2)) == []
    assert list(chunked(["a"], 2)) == [["a"]]
    assert list(chunked(["a", "b", "c", "d", "e"], 2)) == [["a", "b"], ["c", "d"], ["e"]]
