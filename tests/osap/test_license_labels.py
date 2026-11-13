from src.osap.infrastructure.catalogs.index.licenses import normalize_license, resolve_license


def test_normalizes_known_licenses():
    assert normalize_license("publicdomain") == ("Dominio público", None)
    assert normalize_license("Public Domain") == ("Dominio público", None)
    assert normalize_license("cc-zero")[0] == "CC0 1.0"
    assert normalize_license("CPDL")[0] == "Licencia CPDL"
    assert normalize_license("Personal")[0] == "Licencia personal del editor"
    assert normalize_license("Creative Commons Attribution Share Alike")[0] == "CC BY-SA 4.0"
    assert normalize_license("Creative Commons Attribution Non-Commercial")[0] == "CC BY-NC 4.0"


def test_rejects_corpus_markers_and_junk():
    assert normalize_license("PDMX") is None
    assert normalize_license("Religious") is None
    assert normalize_license("") is None
    assert normalize_license("Genoteerd door Van der Elst Johan") is None
    assert normalize_license("\ufffd") is None


def test_representation_license_wins_and_work_is_fallback():
    rep = resolve_license("CPDL", "Public Domain")
    assert rep == {
        "license": "Licencia CPDL",
        "license_url": "https://www.cpdl.org/wiki/index.php/CPDL:Licensing",
        "license_source": "representation",
        "license_raw": "CPDL",
    }
    fallback = resolve_license("PDMX", "cc-zero")
    assert fallback["license"] == "CC0 1.0"
    assert fallback["license_source"] == "works"
    assert resolve_license("PDMX", None) is None

def test_candidate_con_solo_source_url_no_falla():
    from src.osap.infrastructure.catalogs.index.index_catalog_provider import _row_to_candidate

    row = {
        "id": 1,
        "public_id": "index-1",
        "provider": "omr",
        "format": "musicxml",
        "composer_name": "Compositor",
        "title": "Obra",
        "catalogue": None,
        "year": None,
        "download_url": "/api/download/1",
        "resource_id": 123,
        "available": True,
        "source_rep_id": "1",
        "title_provider": "Obra",
        "instrumentation": None,
    }
    candidate = _row_to_candidate(row, {"source_url": "https://example.org/obra"})

    assert candidate.license is None
    assert (candidate.metadata or {}).get("source_url") == "https://example.org/obra"
