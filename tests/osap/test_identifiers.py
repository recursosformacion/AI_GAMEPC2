"""Identificadores — archive por obra/autor, cliente CISAC y enriquecimiento abierto."""

from __future__ import annotations

from src.osap.infrastructure.identifiers import open_sources
from src.osap.infrastructure.identifiers.archive import ComposerRecord, IdentifierArchive, WorkRecord
from src.osap.infrastructure.identifiers.cisac_client import CisacClient


class _Resp:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self._payload


def test_archive_roundtrip_by_author_and_work(tmp_path) -> None:
    archive = IdentifierArchive(tmp_path)
    archive.upsert_composer(
        ComposerRecord(composer_key="wa mozart", canonical_name="Wolfgang Amadeus Mozart",
                       isni="0000000121269154", wikidata="Q254", viaf="32197206", source="test")
    )
    archive.upsert_work(
        WorkRecord(work_key="ave verum corpus", title="Ave Verum Corpus", iswc=None, source="test")
    )
    c = archive.get_composer("wa mozart")
    assert c is not None and c.isni == "0000000121269154"
    w = archive.get_work("ave verum corpus")
    assert w is not None and w.title == "Ave Verum Corpus"

    # Recarga desde fichero (persistencia).
    archive2 = IdentifierArchive(tmp_path)
    assert archive2.get_composer("wa mozart").viaf == "32197206"
    assert archive2.get_work("ave verum corpus") is not None


def test_cisac_client_inactive_without_credentials() -> None:
    client = CisacClient()
    assert client.available is False
    assert client.ipi_context_search("Mozart", ["Ave Verum"]) == []
    assert client.lookup_work("T-000.000.000-0") is None


def test_composer_identifiers_from_wikidata(monkeypatch) -> None:
    def fake_get(url, params=None, **kw):
        if url == open_sources._WIKIDATA_API:
            return _Resp({"search": [{"id": "Q254"}]})
        # SPARQL
        return _Resp(
            {"results": {"bindings": [
                {"itemLabel": {"value": "Wolfgang Amadeus Mozart"},
                 "viaf": {"value": "32197206"}, "isni": {"value": "0000000121269154"},
                 "mbid": {"value": "mb1"}, "alias": {"value": "Mozart"}},
            ]}}
        )

    monkeypatch.setattr(open_sources.requests, "get", fake_get)
    rec = open_sources.composer_identifiers("Wolfgang Amadeus Mozart")
    assert rec is not None
    assert rec.wikidata == "Q254"
    assert rec.isni == "0000000121269154"
    assert rec.viaf == "32197206"
    assert "Mozart" in rec.aliases


def test_work_iswc_best_effort(monkeypatch) -> None:
    monkeypatch.setattr(open_sources, "_musicbrainz_work_mbid", lambda title: "mb-work-1")
    monkeypatch.setattr(open_sources, "_musicbrainz_work_iswc", lambda mbid: "T-001.234.567-8")
    assert open_sources.work_iswc("Ave Verum Corpus") == "T-001.234.567-8"
    assert open_sources.work_iswc("") is None
