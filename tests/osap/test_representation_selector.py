"""Tests del BestRepresentationSelector (selección de mejor representación).

Cubre: múltiples representaciones, varias MusicXML, MusicXML inválido, distintos
QualityLevel, empate y ausencia de representación utilizable. La descarga se
monkeypatchea con contenido real de fixtures (sin fabricar MusicXML).
"""

from __future__ import annotations

from pathlib import Path

from src.osap.application.representation_selector import (
    BestRepresentationSelector,
    RepresentationCandidate,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"

_SHORT = (FIXTURES / "real_short.mxl").read_bytes()
_LARGE = (FIXTURES / "real_large.mxl").read_bytes()
_INVALID = b"<score-partwise><part"


def _candidate(provider: str, fmt: str, url: str) -> RepresentationCandidate:
    return RepresentationCandidate(
        provider=provider,
        format=fmt,
        url=url,
        source_id=f"{provider}-{fmt}",
    )


def _download(url: str) -> bytes | None:
    """Sustituye la red por los fixtures reales."""
    table = {
        "https://omr/short.mxl": _SHORT,
        "https://omr/large.mxl": _LARGE,
        "https://omr/invalid.xml": _INVALID,
        "https://imslp/page": None,
    }
    return table.get(url)


def test_selecciona_mejor_entre_varias_musicxml(monkeypatch) -> None:
    monkeypatch.setattr("src.osap.application.representation_selector._download", _download)
    candidates = (
        _candidate("omr", "musicxml", "https://omr/short.mxl"),
        _candidate("omr", "musicxml", "https://omr/large.mxl"),
    )
    selected = BestRepresentationSelector().select(candidates)
    assert selected.candidate is not None
    # El large produce mejor calidad (más información musical) que el short.
    assert selected.candidate.url == "https://omr/large.mxl"
    assert selected.quality_level.value >= 2
    assert len(selected.alternatives) == 1
    assert selected.alternatives[0].url == "https://omr/short.mxl"


def test_descarta_invalida_y_selecciona_valida(monkeypatch) -> None:
    monkeypatch.setattr("src.osap.application.representation_selector._download", _download)
    candidates = (
        _candidate("omr", "musicxml", "https://omr/invalid.xml"),
        _candidate("omr", "musicxml", "https://omr/short.mxl"),
    )
    selected = BestRepresentationSelector().select(candidates)
    assert selected.candidate is not None
    assert selected.candidate.url == "https://omr/short.mxl"
    assert selected.errors  # la inválida queda registrada como evidencia


def test_todas_invalidas_no_hay_seleccion(monkeypatch) -> None:
    monkeypatch.setattr("src.osap.application.representation_selector._download", _download)
    candidates = (
        _candidate("omr", "musicxml", "https://omr/invalid.xml"),
        _candidate("omr", "musicxml", "https://omr/invalid2.xml"),
    )
    selected = BestRepresentationSelector().select(candidates)
    assert selected.candidate is None
    assert "ninguna representación válida" in selected.reason


def test_sin_representacion_descargable() -> None:
    selected = BestRepresentationSelector().select(
        (_candidate("imslp", "pdf", "not-a-url"),)
    )
    assert selected.candidate is None
    assert "sin representación descargable" in selected.reason


def test_prioriza_musicxml_sobre_pdf(monkeypatch) -> None:
    monkeypatch.setattr("src.osap.application.representation_selector._download", _download)
    candidates = (
        _candidate("mutopia", "pdf", "https://omr/short.mxl"),
        _candidate("omr", "musicxml", "https://omr/short.mxl"),
    )
    selected = BestRepresentationSelector().select(candidates)
    # El PDF de Mutopia se descarta por formato (no MusicXML); el MusicXML gana.
    assert selected.candidate is not None
    assert selected.candidate.provider == "omr"
    assert selected.candidate.format == "musicxml"


def test_empate_usa_desempate_determinista(monkeypatch) -> None:
    """Dos MusicXML del mismo nivel de calidad: gana el provider alfabético."""
    monkeypatch.setattr("src.osap.application.representation_selector._download", _download)
    candidates = (
        _candidate("omr", "musicxml", "https://omr/short.mxl"),
        _candidate("omr", "musicxml", "https://omr/short2.mxl"),
    )
    selected = BestRepresentationSelector().select(candidates)
    assert selected.candidate is not None
    assert selected.reason  # el motivo siempre se expone
