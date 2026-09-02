"""Selección de la mejor representación musical entre las adquiridas.

Reutiliza los modelos existentes (Score, QualityLevel, QualityReport) y el
ScoreValidationStage (BasicValidator → MusicXmlValidator). No inventa un sistema
de calidad paralelo: el criterio es explícito y documentado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.pipeline_context import PipelineContext
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.value_objects import Confidence, Duration, ProviderId, SourceId
from src.osap.infrastructure.pipeline.score_validation_stage import (
    KEY_ACQUISITION,
    KEY_SCORE,
    ScoreValidationError,
    ScoreValidationStage,
)

# Formatos con fichero musical real (frente a páginas de proveedor).
_SCORE_FORMATS = {"musicxml", "mxl", "mei"}


@dataclass(frozen=True)
class RepresentationCandidate:
    """Una representación descubierta en un provider, con URL descargable."""

    provider: str
    format: str
    url: str
    source_id: str


@dataclass(frozen=True)
class SelectedRepresentation:
    """Resultado de la selección: la mejor representación y sus alternativas."""

    candidate: RepresentationCandidate | None
    score: object | None = None
    quality_level: QualityLevel = QualityLevel.UNREADABLE
    report: object | None = None
    reason: str = ""
    alternatives: tuple[RepresentationCandidate, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


class BestRepresentationSelector:
    """Selecciona la mejor representación descargable y la valida.

    Criterio de selección (explícito, en orden):
      1. representación descargable;
      2. formato con fichero musical (MusicXML/MXL/MEI) frente a página/proveedor;
      3. validación MusicXML: se descartan las que fallan (Score no válido);
      4. mayor `QualityLevel`;
      5. mejor `QualityReport.overall()` (desempate dentro del mismo nivel);
      6. menos errores/warnings relevantes;
      7. desempate final: provider (orden alfabético, determinista).

    El motivo de la elección se expone en `SelectedRepresentation.reason`. Las
    demás candidatas se conservan como alternativas/evidencia.
    """

    def select(
        self,
        candidates: tuple[RepresentationCandidate, ...],
    ) -> SelectedRepresentation:
        usable = [c for c in candidates if c.url.startswith(("http://", "https://"))]
        if not usable:
            return SelectedRepresentation(
                candidate=None,
                reason="sin representación descargable",
                alternatives=candidates,
            )

        # Orden determinista (provider+formato) antes de evaluar.
        usable = sorted(usable, key=lambda c: (c.provider, c.format))

        validated: list[tuple[RepresentationCandidate, AcquisitionResult, object, str]] = []
        errors: list[str] = []
        for c in usable:
            content = _download(c.url)
            if content is None:
                errors.append(f"{c.provider}:{c.format}: descarga fallida")
                continue
            acquisition = AcquisitionResult(
                provider_id=ProviderId(c.provider),
                source=_source(c, content),
                confidence=Confidence(1.0),
                processing_time=Duration(0.0),
                format=_output_format(c.format),
            )
            try:
                ctx = ScoreValidationStage().execute(PipelineContext(data={KEY_ACQUISITION: acquisition}))
                score = ctx.data.get(KEY_SCORE)
                if score is None:
                    errors.append(f"{c.provider}:{c.format}: sin Score")
                    continue
                validated.append((c, acquisition, score, _reason_of(c, score)))
            except ScoreValidationError as exc:
                errors.append(f"{c.provider}:{c.format}: invalidación: {exc}")

        if not validated:
            return SelectedRepresentation(
                candidate=None,
                reason="ninguna representación válida tras validación",
                alternatives=candidates,
                errors=tuple(errors),
            )

        # Selección por criterio (mayor calidad). Desempates explícitos.
        def key(item: tuple[RepresentationCandidate, AcquisitionResult, object, str]) -> tuple[object, ...]:
            c, _acq, score, _reason = item
            ql = _quality_level(score)
            overall = _report_overall(score)
            n_errors = len(_score_errors(score))
            n_warnings = len(_score_warnings(score))
            is_score_format = 1 if c.format.lower() in _SCORE_FORMATS else 0
            return (is_score_format, ql.value, overall, -n_errors, -n_warnings, c.provider)

        best_c, best_acq, best_score, best_reason = max(validated, key=key)
        chosen = best_c
        reason = best_reason or _default_reason(chosen, best_score)
        alternatives = tuple(c for c, _a, _s, _r in validated if c != chosen)
        warnings = _score_warnings(best_score)
        return SelectedRepresentation(
            candidate=chosen,
            score=best_score,
            quality_level=_quality_level(best_score),
            report=_report_of(best_score),
            reason=reason,
            alternatives=alternatives,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )


def _source(c: RepresentationCandidate, content: bytes) -> MusicalSource:
    return MusicalSource(
        source_id=SourceId(c.source_id),
        content=content,
        format=_output_format(c.format),
        metadata={},
    )


def _output_format(fmt: str) -> OutputFormat:
    f = fmt.lower()
    if f == "musicxml":
        return OutputFormat.MUSICXML
    if f == "mxl":
        return OutputFormat.MUSICXML
    if f == "mei":
        return OutputFormat.MEI
    if f == "pdf":
        return OutputFormat.PDF
    if f == "midi":
        return OutputFormat.MIDI
    return OutputFormat.MUSICXML


def _download(url: str) -> bytes | None:
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "osap-api/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw: bytes = resp.read()
            return raw
    except Exception:  # noqa: BLE001
        return None


def _report_of(score: object) -> object:
    md = getattr(score, "metadata", {})
    if isinstance(md, dict):
        return md.get("quality_report")
    return None


def _report_overall(score: object) -> float:
    report = _report_of(score)
    overall = getattr(report, "overall", None)
    if callable(overall):
        try:
            return float(overall())
        except Exception:  # noqa: BLE001
            return 0.0
    return 0.0


def _quality_level(score: object) -> QualityLevel:
    return getattr(score, "quality_level", None) or QualityLevel.UNREADABLE


def _score_errors(score: object) -> list[str]:
    md = getattr(score, "metadata", {})
    if isinstance(md, dict):
        err = md.get("errors")
        if isinstance(err, (list, tuple)):
            return [str(e) for e in err]
    return []


def _score_warnings(score: object) -> list[str]:
    md = getattr(score, "metadata", {})
    if isinstance(md, dict):
        warn = md.get("warnings")
        if isinstance(warn, (list, tuple)):
            return [str(w) for w in warn]
    return []


def _reason_of(c: RepresentationCandidate, score: object) -> str:
    parts = [
        f"formato {c.format}",
        f"QualityLevel {_quality_level(score).value}",
    ]
    overall = _report_overall(score)
    if overall:
        parts.append(f"QualityReport {overall:.2f}")
    return "; ".join(parts)


def _default_reason(c: RepresentationCandidate, score: object) -> str:
    return f"mayor calidad entre las representaciones válidas ({c.provider} · {c.format})"
