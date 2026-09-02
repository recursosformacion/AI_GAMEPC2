"""Generador mínimo y funcional de materiales de estudio (estructura textual).

Produce un `StudyMaterial` de tipo `EXERCISE` cuyo contenido es un resumen
estructural del `Score`: información REAL presente en el Score validado por OSAP
(título, compositor, partes, compases, notas, voces, letra, nivel de calidad y
dimensiones del QualityReport). No inventa información musical que no exista en
el Score.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.chorus.domain.material_type import MaterialType
from src.chorus.domain.study_material import StudyMaterial
from src.chorus.ports.study_material_generator import IStudyMaterialGenerator
from src.osap.domain.quality_report import QualityReport

if TYPE_CHECKING:
    from src.osap.domain.score import Score

# Tipos que este generador puede producir.
_SUPPORTED = (MaterialType.EXERCISE,)


class ExerciseGenerator(IStudyMaterialGenerator):
    """Genera un material de ejercicio (resumen estructural textual) desde un Score."""

    @property
    def name(self) -> str:
        return "exercise_generator"

    def generate(self, score: Score, material_type: MaterialType, voice: str | None = None) -> StudyMaterial:
        if material_type not in _SUPPORTED:
            raise ValueError(f"{self.name} no soporta {material_type.value}")
        metadata = _metadata(score)
        content = _content(score, metadata, voice)
        return StudyMaterial(
            material_type=material_type,
            content=content,
            voice=voice,
            metadata=metadata,
        )


def _metadata(score: Score) -> dict[str, object]:
    md = score.metadata
    report = md.get("quality_report")
    dims: dict[str, float] = {}
    if isinstance(report, QualityReport):
        dims = {d.value: round(float(s), 3) for d, s in report.dimensions.items()}
    return {
        "title": score.title,
        "composer": score.composer,
        "quality_level": score.quality_level.value,
        "parts": _int_or_none(md.get("parts")),
        "measures": _int_or_none(md.get("measures")),
        "notes": _int_or_none(md.get("notes")),
        "voices": _int_or_none(md.get("voices")),
        "has_lyrics": bool(md.get("has_lyrics")),
        "quality_report": dims,
        "errors": [str(e) for e in _list_or_empty(md.get("errors"))],
        "warnings": [str(w) for w in _list_or_empty(md.get("warnings"))],
        "generator": "exercise_generator",
    }


def _content(score: Score, metadata: dict[str, object], voice: str | None) -> dict[str, object]:
    """Contenido del material: solo información real del Score, sin inventar."""
    parts = metadata.get("parts")
    measures = metadata.get("measures")
    notes = metadata.get("notes")
    voices = metadata.get("voices")
    has_lyrics = metadata.get("has_lyrics")
    report = metadata.get("quality_report") or {}
    lines: list[str] = []
    if score.title:
        lines.append(f"Título: {score.title}")
    if score.composer:
        lines.append(f"Compositor: {score.composer}")
    if parts is not None:
        lines.append(f"Partes: {parts}")
    if measures is not None:
        lines.append(f"Compases: {measures}")
    if notes is not None:
        lines.append(f"Notas: {notes}")
    if voices is not None:
        lines.append(f"Voces: {voices}")
    if has_lyrics is not None:
        lines.append(f"Con letra: {'sí' if has_lyrics else 'no'}")
    lines.append(f"Calidad (QualityLevel): {metadata.get('quality_level')}")
    report = metadata.get("quality_report")
    if isinstance(report, dict) and report:
        dims_desc = ", ".join(f"{k}={v}" for k, v in sorted(report.items()))
        lines.append(f"QualityReport: {dims_desc}")
    if voice:
        lines.append(f"Voz solicitada: {voice}")
    return {"text": "\n".join(lines)}


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _list_or_empty(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []
