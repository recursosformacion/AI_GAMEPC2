"""Tests del provider CPDL (osap-api).

Verifican que CPDLCatalogProvider.search consulta el circuito real de osap-storage
(/api/v1/cpdl/search) con `q` y los términos de voicing, y que cada página CPDL
produce UN candidato que conserva su origen (cpdl_page_id, page_url, voicing).
"""

from __future__ import annotations

import requests

from src.osap.domain.search_request import SearchRequestBuilder
from src.osap.infrastructure.catalogs.cpdl import CPDLCatalogProvider


class _FakeResponse:
    def __init__(self, payload: list[dict]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


def _provider() -> CPDLCatalogProvider:
    return CPDLCatalogProvider(base_url="http://storage.example")


def _row(page_id: int, title: str, composer: str, voicing: list[str]) -> dict:
    return {
        "id": page_id,
        "page_title": f"{title} ({composer})",
        "title": title,
        "composer": composer,
        "catalogue_hint": None,
        "voicing_terms": voicing,
        "page_url": f"https://www.cpdl.org/wiki/index.php?title={title}",
    }


def test_sin_criterios_no_consulta(monkeypatch) -> None:
    llamado: list[bool] = []

    def _get(*args, **kwargs) -> object:  # noqa: ARG001
        llamado.append(True)
        return _FakeResponse([])

    monkeypatch.setattr(requests, "get", _get)
    provider = _provider()
    assert provider.search(SearchRequestBuilder().build()) == ()
    assert not llamado


def test_q_mas_voicing(monkeypatch) -> None:
    capturado: dict[str, object] = {}

    def _get(url: str, params: list[tuple[str, str]], headers: dict, timeout: float) -> _FakeResponse:
        capturado["url"] = url
        capturado["params"] = params
        capturado["headers"] = headers
        return _FakeResponse(
            [_row(42, "In monte Oliveti", "Giovanni Croce", ["SATB", "STTB", "AATB", "ATTB"])]
        )

    monkeypatch.setattr(requests, "get", _get)
    provider = _provider()
    req = (
        SearchRequestBuilder()
        .text("In monte Oliveti")
        .voices("SATB", "satb")
        .build()
    )
    results = provider.search(req)
    assert len(results) == 1
    assert capturado["url"] == "http://storage.example/api/v1/cpdl/search"
    params = capturado["params"]
    assert ("q", "In monte Oliveti") in params
    assert ("voicing", "SATB") in params
    rep = results[0]
    assert rep.provider_id.value == "cpdl"
    assert rep.view_url.endswith("title=In monte Oliveti")
    md = rep.metadata or {}
    assert md["cpdl_page_id"] == 42
    assert md["voicing"] == ["SATB", "STTB", "AATB", "ATTB"]
    assert rep.downloadable is False


def test_dedup_de_terminos_y_unica_pagina(monkeypatch) -> None:
    capturado: dict[str, object] = {}

    def _get(url: str, params: list[tuple[str, str]], headers: dict, timeout: float) -> _FakeResponse:
        capturado["params"] = params
        return _FakeResponse(
            [
                _row(1, "Obra A", "Compositor A", ["SATB"]),
                _row(2, "Obra B", "Compositor B", ["SATB"]),
            ]
        )

    monkeypatch.setattr(requests, "get", _get)
    provider = _provider()
    req = SearchRequestBuilder().voices("SATB", "SATB").build()
    results = provider.search(req)
    # Solo se envía UNA vez el término repetido (dedup) y hay un candidato por página.
    voces = [p[1] for p in capturado["params"] if p[0] == "voicing"]  # type: ignore[union-attr]
    assert voces == ["SATB"]
    assert len(results) == 2
    assert {r.work_descriptor.title for r in results} == {"Obra A", "Obra B"}
