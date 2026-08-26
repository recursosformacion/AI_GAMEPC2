"""Validación real de MusicXML por niveles.

El objetivo NO es un compilador MusicXML completo, sino detectar de forma
automática los errores que hagan una partitura inutilizable, parcialmente
utilizable o utilizable con advertencias.

Niveles:

  Nivel 0 — XML inválido
      XML mal formado, encoding inválido, documento vacío, root incorrecto.

  Nivel 1 — MusicXML estructuralmente reconocible
      `score-partwise`, `part-list`, `score-part`, `part`, `measure`.

  Nivel 2 — contenido musical mínimamente utilizable
      notes, rests, durations, divisions, voices, staff, time signature,
      consistencia básica de duraciones, referencias a parts existentes.

  Nivel 3 — calidad suficiente para procesamiento
      `QualityReport` con dimensiones independientes (STRUCTURE, NOTATION,
      VOICES, LYRICS) y `QualityLevel` derivado.

Limitaciones explícitas (no simuladas): no se reproduce MuseScore ni se
validan reglas de armonía/contrapunto ni el DTD completo.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.osap.domain.quality_report import QualityDimension, QualityReport
from src.osap.domain.score import Score
from src.osap.domain.value_objects import ScoreId
from src.osap.infrastructure.validation.musicxml_extraction import (
    MusicXmlExtractionError,
    extract_musicxml,
)

if TYPE_CHECKING:
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.quality_level import QualityLevel


@dataclass(frozen=True)
class MusicXmlReport:
    """Resultado intermedio del validador (errores, warnings, dimensiones)."""

    well_formed: bool = False
    is_musicxml: bool = False
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    part_count: int = 0
    measure_count: int = 0
    note_count: int = 0
    voice_count: int = 0
    has_lyrics: bool = False
    has_time_signature: bool = False
    dimensions: dict[QualityDimension, float] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.is_musicxml and not self.errors

    def quality_report(self) -> QualityReport:
        return QualityReport(dimensions=dict(self.dimensions))

    def quality_level(self) -> QualityLevel:
        return self.quality_report().quality_level()


class MusicXmlValidator:
    """Valida un `AcquisitionResult` cuyo contenido es MusicXML (o .mxl)."""

    name = "musicxml_validator"

    def validate(self, result: AcquisitionResult) -> Score:
        source = result.source
        try:
            xml_text = extract_musicxml(source.content)
        except MusicXmlExtractionError as exc:
            return self._invalid_score(result, f"extracción: {exc}")
        report = self._analyze(xml_text)
        return self._build_score(result, report)

    # ------------------------------------------------------------------ análisis

    def _analyze(self, xml_text: str) -> MusicXmlReport:
        if not xml_text.strip():
            return MusicXmlReport(errors=("documento vacío",))

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return MusicXmlReport(
                well_formed=False,
                errors=(f"XML mal formado: {exc}",),
            )

        tag = _local_name(root.tag)
        if tag != "score-partwise":
            return MusicXmlReport(
                well_formed=True,
                is_musicxml=False,
                errors=(f"root incorrecto: {tag or '(sin nombre)'}",),
            )

        errors: list[str] = []
        warnings: list[str] = []

        # ---- Nivel 1: estructura ----
        part_list = root.find("./part-list")
        if part_list is None:
            errors.append("falta part-list")

        parts = root.findall("./part")
        part_ids = [str(p.get("id") or "") for p in parts]
        if part_list is None and not part_ids:
            errors.append("sin part-list ni part")

        if part_list is not None:
            score_parts = part_list.findall("./score-part")
            if not score_parts:
                errors.append("part-list vacío")

        measures = root.findall("./part/measure")
        if not measures:
            errors.append("sin measure")

        # ---- Nivel 2: contenido musical ----
        notes = root.findall(".//note")
        rests = root.findall(".//note/rest")
        if not notes:
            errors.append("sin notas")
        elif rests and not any(n.find("pitch") is not None for n in notes):
            warnings.append("solo silencios")

        divisions = root.findall(".//divisions")
        if notes and not divisions:
            warnings.append("sin divisions (duraciones ambiguas)")

        durations = [d for d in root.findall(".//duration")]
        if notes and not durations:
            warnings.append("notas sin duration")

        voices = root.findall(".//voice")
        voice_numbers = sorted({int(v.text) for v in voices if v.text and v.text.isdigit()})
        if len(voice_numbers) > 1:
            warnings.append(f"múltiples voces: {voice_numbers}")

        staves = root.findall(".//staff")
        if staves:
            staff_numbers = sorted({int(s.text) for s in staves if s.text and s.text.isdigit()})
            if len(staff_numbers) > 1:
                warnings.append(f"múltiples staves: {staff_numbers}")

        time_sig = root.findall(".//time")
        has_time = bool(time_sig)

        lyrics = root.findall(".//lyric")
        has_lyrics = bool(lyrics)

        # referencias a part inexistente: toda `part` debe estar declarada en
        # `part-list` (si part-list existe) o tener al menos un measure.
        declared_ids: set[str] = set()
        if part_list is not None:
            declared_ids = {str(sp.get("id") or "") for sp in part_list.findall("./score-part")}
        for p in parts:
            pid = str(p.get("id") or "")
            if declared_ids and pid not in declared_ids:
                errors.append(f"part no declarada en part-list: {pid!r}")
            if not pid:
                errors.append("part sin id")

        # consistencia básica de duraciones: divisions y duration numéricos
        self._check_durations(root, notes, warnings)

        note_count = len(notes)
        part_count = len(part_ids)
        measure_count = len(measures)
        voice_count = len(voice_numbers)

        # ---- Nivel 3: dimensiones de calidad ----
        dims = {
            QualityDimension.STRUCTURE: self._dim_structure(errors, part_count, measure_count),
            QualityDimension.NOTATION: self._dim_notation(errors, warnings, note_count, has_time, bool(divisions)),
            QualityDimension.VOICES: self._dim_voices(warnings, voice_count),
            QualityDimension.LYRICS: self._dim_lyrics(has_lyrics),
        }

        return MusicXmlReport(
            well_formed=True,
            is_musicxml=True,
            errors=tuple(errors),
            warnings=tuple(warnings),
            part_count=part_count,
            measure_count=measure_count,
            note_count=note_count,
            voice_count=voice_count,
            has_lyrics=has_lyrics,
            has_time_signature=has_time,
            dimensions=dims,
        )

    @staticmethod
    def _check_durations(root: ET.Element, notes: list[ET.Element], warnings: list[str]) -> None:
        dur_values = [d.text for d in root.findall(".//duration") if d.text]
        if not dur_values:
            return
        bad = [d for d in dur_values if not d.isdigit()]
        if bad:
            warnings.append(f"durations no numéricas: {bad[:3]}")
        # divisions==0 provoca divisiones por cero al procesar.
        for div in root.findall(".//divisions"):
            if div.text and div.text.strip() == "0":
                warnings.append("divisions=0 (duraciones indeterminadas)")

    # ---- dimensiones ----

    @staticmethod
    def _dim_structure(errors: list[str], part_count: int, measure_count: int) -> float:
        if errors and any("part-list" in e or "part" in e or "measure" in e for e in errors):
            return 0.0
        if part_count == 0 or measure_count == 0:
            return 0.2
        return min(1.0, 0.5 + 0.1 * min(part_count, 5) + 0.05 * min(measure_count, 10))

    @staticmethod
    def _dim_notation(
        errors: list[str], warnings: list[str], note_count: int, has_time: bool, has_divisions: bool
    ) -> float:
        if errors and any("sin notas" in e or "duration" in e for e in errors):
            return 0.0
        score = 0.0
        if note_count > 0:
            score += 0.6
        if has_divisions:
            score += 0.2
        if has_time:
            score += 0.1
        if any("duration" in w or "divisions" in w for w in warnings):
            score -= 0.1
        return max(0.0, min(1.0, score))

    @staticmethod
    def _dim_voices(warnings: list[str], voice_count: int) -> float:
        if voice_count <= 1:
            return 0.3  # monofónico: funcional pero sin riqueza polifónica
        if voice_count >= 4:
            return 1.0
        return 0.4 + 0.15 * voice_count

    @staticmethod
    def _dim_lyrics(has_lyrics: bool) -> float:
        return 1.0 if has_lyrics else 0.0

    # ------------------------------------------------------------------ score

    def _invalid_score(self, result: AcquisitionResult, reason: str) -> Score:
        report = MusicXmlReport(errors=(reason,))
        return self._build_score(result, report)

    def _build_score(self, result: AcquisitionResult, report: MusicXmlReport) -> Score:
        source = result.source
        title = str(source.metadata.get("title") or "") or None
        composer = str(source.metadata.get("composer") or "") or None
        return Score(
            score_id=ScoreId(f"score-{source.source_id.value}"),
            content=source.content,
            title=title,
            composer=composer,
            quality_level=report.quality_level(),
            metadata={
                "valid": report.usable,
                "errors": list(report.errors),
                "warnings": list(report.warnings),
                "parts": report.part_count,
                "measures": report.measure_count,
                "notes": report.note_count,
                "voices": report.voice_count,
                "has_lyrics": report.has_lyrics,
                "quality_report": report.quality_report(),
            },
        )


def _local_name(tag: str) -> str:
    """Devuelve el nombre local de un tag (ignora prefijos de namespace)."""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag
