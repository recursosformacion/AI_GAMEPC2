"""Mapeo de `works_resources_type` CPDL a formato de índice (sin disfrazar)."""

from script.index_works import _cpdl_format


def test_formatos_equivalentes() -> None:
    assert _cpdl_format("MXL") == "musicxml"
    assert _cpdl_format("MusicXML") == "musicxml"
    assert _cpdl_format("MIDI") == "midi"
    assert _cpdl_format("mid") == "midi"
    assert _cpdl_format("PDF") == "pdf"


def test_formatos_propios_no_se_convierten_en_musicxml() -> None:
    assert _cpdl_format("MUS") == "mus"
    assert _cpdl_format("SIB") == "sib"
    assert _cpdl_format("MSCZ") == "mscz"
    assert _cpdl_format("CAPX") == "capx"
    assert _cpdl_format("MP3") == "audio"


def test_tipo_desconocido_se_descarta() -> None:
    assert _cpdl_format(None) is None
    assert _cpdl_format("") is None
    assert _cpdl_format("ZIP") is None
