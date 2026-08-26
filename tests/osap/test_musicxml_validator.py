"""Tests del validador MusicXML por niveles (BasicValidator / MusicXmlValidator).

Cubre los 12 casos exigidos + fixtures reales del corpus OMR (.mxl).
"""

from pathlib import Path
from typing import Any, cast

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.value_objects import Confidence, Duration, ProviderId, SourceId
from src.osap.infrastructure.adapters.validation.basic_validator import BasicValidator
from src.osap.infrastructure.validation.musicxml_extraction import extract_musicxml
from src.osap.infrastructure.validation.musicxml_validator import MusicXmlValidator

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"


def _md(score: Any) -> dict[str, Any]:
    """Metadata tipada del Score para asserts (el dict es `dict[str, object]`)."""
    return cast("dict[str, Any]", score.metadata)


def _source(content: object) -> MusicalSource:
    return MusicalSource(source_id=SourceId("s-1"), content=content, format=OutputFormat.MUSICXML)


def _result(content: object) -> AcquisitionResult:
    return AcquisitionResult(
        provider_id=ProviderId("test"),
        source=_source(content),
        confidence=Confidence(0.9),
        processing_time=Duration(0.1),
        format=OutputFormat.MUSICXML,
    )


VALID_MINIMAL = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Voice</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice></note>
      <note><rest/><duration>3</duration><voice>1</voice></note>
    </measure>
  </part>
</score-partwise>
"""


def test_1_valid_minimal() -> None:
    score = MusicXmlValidator().validate(_result(VALID_MINIMAL))
    assert _md(score)["valid"] is True
    assert _md(score)["errors"] == []
    assert score.quality_level != QualityLevel.UNREADABLE
    assert _md(score)["notes"] >= 2
    assert _md(score)["parts"] == 1


def test_2_malformed_xml() -> None:
    score = MusicXmlValidator().validate(_result("<score-partwise><part"))
    assert _md(score)["valid"] is False
    assert any("XML mal formado" in e for e in _md(score)["errors"])
    assert score.quality_level == QualityLevel.UNREADABLE


def test_3_not_musicxml() -> None:
    score = MusicXmlValidator().validate(_result("<html><body>hola</body></html>"))
    assert _md(score)["valid"] is False
    assert any("root incorrecto" in e for e in _md(score)["errors"])


def test_4_missing_part_list() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1"><part id="P1">
    <measure number="1"><note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure>
    </part></score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is False
    assert any("falta part-list" in e for e in _md(score)["errors"])


def test_5_invalid_part() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1">
    <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
    <part id="P2"><measure number="1">
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
    </measure></part>
    </score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is False
    assert any("no declarada" in e for e in _md(score)["errors"])


def test_6_measure_without_content() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1">
    <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
    <part id="P1"><measure number="1"></measure></part>
    </score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is False
    assert any("sin notas" in e for e in _md(score)["errors"])


def test_7_incoherent_durations() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1">
    <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
    <part id="P1">
      <measure number="1">
        <attributes><divisions>0</divisions></attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>abc</duration></note>
      </measure>
    </part>
    </score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is True  # usable
    assert any("durations no numéricas" in w for w in _md(score)["warnings"])
    assert any("divisions=0" in w for w in _md(score)["warnings"])
    assert score.quality_level == QualityLevel.PARTIAL_STRUCTURE


def test_8_measure_reference_broken_part() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1">
    <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
    <part id="P1">
      <measure number="1"><attributes><divisions>1</divisions></attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure>
    </part>
    <part id="P2">
      <measure number="1"><note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration></note></measure>
    </part>
    </score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is False
    assert any("no declarada" in e for e in _md(score)["errors"])


def test_9_multiple_voices() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1">
    <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
    <part id="P1"><measure number="1"><attributes><divisions>1</divisions></attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><voice>2</voice></note>
    </measure></part></score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is True
    assert any("múltiples voces" in w for w in _md(score)["warnings"])
    assert _md(score)["voices"] == 2


def test_10_lyrics_present() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1">
    <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
    <part id="P1"><measure number="1"><attributes><divisions>1</divisions></attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>
        <lyric><syllabic>single</syllabic><text>Hola</text></lyric></note>
    </measure></part></score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is True
    assert _md(score)["has_lyrics"] is True
    assert score.quality_level in (QualityLevel.FULL_NOTATION, QualityLevel.BASIC_MELODY)


def test_11_warnings_but_usable() -> None:
    xml = """<?xml version="1.0"?><score-partwise version="3.1">
    <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
    <part id="P1"><measure number="1"><attributes><divisions>1</divisions></attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
      <note><rest/><duration>1</duration></note>
    </measure></part></score-partwise>"""
    score = MusicXmlValidator().validate(_result(xml))
    assert _md(score)["valid"] is True
    assert _md(score)["errors"] == []
    assert score.quality_level != QualityLevel.UNREADABLE


def test_12_unusable() -> None:
    # XML vacío → inutilizable.
    score = MusicXmlValidator().validate(_result(""))
    assert _md(score)["valid"] is False
    assert score.quality_level == QualityLevel.UNREADABLE


def test_real_short_mxl() -> None:
    content = (FIXTURES / "real_short.mxl").read_bytes()
    score = MusicXmlValidator().validate(_result(content))
    assert _md(score)["valid"] is True
    assert _md(score)["parts"] == 1
    assert _md(score)["notes"] > 0
    assert score.quality_level != QualityLevel.UNREADABLE


def test_real_large_mxl() -> None:
    content = (FIXTURES / "real_large.mxl").read_bytes()
    score = MusicXmlValidator().validate(_result(content))
    assert _md(score)["valid"] is True
    assert _md(score)["parts"] > 1
    assert _md(score)["measures"] > 100
    assert _md(score)["notes"] > 1000
    assert score.quality_level != QualityLevel.UNREADABLE


def test_basic_validator_delegates() -> None:
    validator = BasicValidator()
    assert validator.name == "basic_validator"
    score = validator.validate(_result(VALID_MINIMAL))
    assert _md(score)["valid"] is True


def test_extraction_supports_plain_and_zip() -> None:
    plain = extract_musicxml(VALID_MINIMAL)
    assert "score-partwise" in plain
    zipped = (FIXTURES / "real_short.mxl").read_bytes()
    extracted = extract_musicxml(zipped)
    assert "score-partwise" in extracted
    # XML plano no-MusicXML: extracción devuelve el texto (el validador lo rechaza luego).
    assert "score-partwise" not in extract_musicxml("<html><body>hola</body></html>")
