"""Tests del conector Wikidata y utilidades IIIF del enriquecimiento multifuente."""

from __future__ import annotations

from typing import Any

from src.osap.application.enrichment import iiif, wikidata
from src.osap.application.enrichment.wikidata import WikidataSource

_PERSON_DOC: dict[str, Any] = {
    "entities": {
        "Q254": {
            "labels": {"es": {"value": "Wolfgang Amadeus Mozart"}},
            "claims": {
                "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1756-01-27T00:00:00Z"}}}}],
                "P570": [{"mainsnak": {"datavalue": {"value": {"time": "+1791-12-05T00:00:00Z"}}}}],
                "P227": [{"mainsnak": {"datavalue": {"value": "118584596"}}}],
                "P214": [{"mainsnak": {"datavalue": {"value": "123456"}}}],
                "P213": [{"mainsnak": {"datavalue": {"value": "0000 0001 0000 0000"}}}],
                "P27": [{"mainsnak": {"datavalue": {"value": {"id": "Q40"}}}}],
                "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q639669"}}}}],
            },
        }
    }
}

_WORK_DOC: dict[str, Any] = {
    "entities": {
        "Q188891": {
            "labels": {"es": {"value": "Eine kleine Nachtmusik"}},
            "claims": {
                "P86": [{"mainsnak": {"datavalue": {"value": {"id": "Q254"}}}}],
                "P571": [{"mainsnak": {"datavalue": {"value": {"time": "+1787-00-00T00:00:00Z"}}}}],
                "P577": [{"mainsnak": {"datavalue": {"value": {"time": "+1827-00-00T00:00:00Z"}}}}],
                "P826": [{"mainsnak": {"datavalue": {"value": {"id": "Q596"}}}}],
                "P870": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q1234"}}}},
                    {"mainsnak": {"datavalue": {"value": {"id": "Q5678"}}}},
                ],
            },
        }
    }
}


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _Session:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append((url, kwargs))
        return _Response(self.payload)


def test_extract_person_scalar_fields() -> None:
    data = wikidata.extract_person(_PERSON_DOC, "Q254")
    assert data["name"] == "Wolfgang Amadeus Mozart"
    assert data["birth_year"] == 1756
    assert data["death_year"] == 1791
    assert data["gnd"] == "118584596"
    assert data["viaf"] == "123456"
    assert data["nationality_qid"] == ["Q40"]
    assert data["occupation_qid"] == ["Q639669"]


def test_extract_work_scalar_and_list_fields() -> None:
    data = wikidata.extract_work(_WORK_DOC, "Q188891")
    assert data["title"] == "Eine kleine Nachtmusik"
    assert data["composer_qid"] == ["Q254"]
    assert data["inception_year"] == 1787
    assert data["publication_year"] == 1827
    assert data["tonality_qid"] == ["Q596"]
    assert data["instrumentation_qid"] == ["Q1234", "Q5678"]


def test_person_candidates_have_provenance() -> None:
    data = wikidata.extract_person(_PERSON_DOC, "Q254")
    cands = wikidata.person_candidates("Q254", data)
    fields = {c.field for c in cands}
    assert {"name", "birth_year", "death_year", "gnd", "nationality_qid"} <= fields
    assert all(c.source == "wikidata" and c.license == "CC0-1.0" for c in cands)
    assert all(c.evidence_url.endswith("Q254") for c in cands)


def test_work_candidates_instrumentation_multiple() -> None:
    data = wikidata.extract_work(_WORK_DOC, "Q188891")
    cands = wikidata.work_candidates("Q188891", data)
    instr = [c.value for c in cands if c.field == "instrumentation_qid"]
    assert instr == ["Q1234", "Q5678"]


def test_search_uses_wbsearchentities() -> None:
    payload = {
        "search": [
            {
                "id": "Q254",
                "label": "Wolfgang Amadeus Mozart",
                "description": "compositor austriaco",
            }
        ]
    }
    session = _Session(payload)
    source = WikidataSource(session=session)
    results = source.search("moxart", "person")
    assert results == [
        {"qid": "Q254", "label": "Wolfgang Amadeus Mozart", "description": "compositor austriaco"}
    ]
    url, kwargs = session.calls[0]
    assert url == wikidata.MEDIAWIKI_API
    assert kwargs["params"]["action"] == "wbsearchentities"
    assert kwargs["params"]["search"] == "moxart"
    assert kwargs["params"]["format"] == "json"


def test_iiif_manifest_detection() -> None:
    assert iiif.looks_like_iiif_manifest(
        {"@context": "http://iiif.io/api/presentation/2/context.json", "@type": "sc:Manifest"}
    )
    assert iiif.looks_like_iiif_manifest({"type": "Manifest"})
    assert not iiif.looks_like_iiif_manifest({"foo": "bar"})
