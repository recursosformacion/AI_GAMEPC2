"""Atribución obra → compositor vía Wikidata (con HTTP mockeado, determinista).

La obra identificada sin compositor se atribuye consultando obras musicales de Wikidata
(P86). Un título tradicional sin obra → sin compositor (desconocido, no anónimo).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.infrastructure.resolvers.wikidata_work_attributor import WikidataWorkAttributor

if TYPE_CHECKING:
    import pytest


class _Resp:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self._payload


def _fake_get(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, params: dict[str, object] | None = None, **kwargs: object) -> _Resp:
        action = (params or {}).get("action")
        if action == "wbsearchentities":
            return _Resp({"search": [{"id": "Q790327"}]})  # obra "Ave Verum Corpus"
        if action == "wbgetentities":
            return _Resp({"entities": {"Q254": {"labels": {"en": {"value": "Mozart"}}}}})
        # SPARQL: la obra Q790327 tiene compositor Mozart (Q254) con VIAF.
        return _Resp(
            {
                "results": {
                    "bindings": [
                        {
                            "composer": {"value": "http://www.wikidata.org/entity/Q254"},
                            "viaf": {"value": "32197206"},
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(
        "src.osap.infrastructure.resolvers.wikidata_work_attributor.requests.get", fake_get
    )


def test_attribute_returns_composer_with_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_get(monkeypatch)
    res = WikidataWorkAttributor().attribute("Ave Verum Corpus")
    assert len(res) == 1
    assert res[0]["composer_qid"] == "Q254"
    assert res[0]["external_ids"]["viaf"] == "32197206"


def test_attribute_returns_empty_for_traditional(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, params: dict[str, object] | None = None, **kwargs: object) -> _Resp:
        return _Resp({"search": []})  # ninguna obra musical coincide

    monkeypatch.setattr(
        "src.osap.infrastructure.resolvers.wikidata_work_attributor.requests.get", fake_get
    )
    res = WikidataWorkAttributor().attribute("Trunch Wassail Song")
    assert res == []


def test_attribute_empty_title() -> None:
    assert WikidataWorkAttributor().attribute("") == []
