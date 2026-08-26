"""Pruebas del Score Acquisition Pipeline (stage de validación + trazabilidad).

Flujo cubierto:
  MusicalDocument → adquisición/representación MusicXML → BasicValidator →
  Score + QualityReport → PipelineLog.

Casos: .mxl válido pequeño, .mxl válido grande, XML mal formado,
estructura incorrecta, sin notas, contenido inválido, y la prueba clave de que
el Score conserva exactamente la información de calidad del validador (no se
aplana ni se pierde el diagnóstico).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.document_type import DocumentType
from src.osap.domain.musical_document import MusicalDocument
from src.osap.domain.musical_request import MusicalRequest
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.pipeline_context import PipelineContext
from src.osap.domain.pipeline_log import PipelineLog
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.quality_report import QualityReport
from src.osap.domain.request_type import RequestType
from src.osap.domain.score import Score
from src.osap.domain.value_objects import (
    Confidence,
    DocumentId,
    Duration,
    ProviderId,
    RequestId,
    SourceId,
)
from src.osap.infrastructure.adapters.validation import BasicValidator
from src.osap.infrastructure.pipeline import (
    KEY_ACQUISITION,
    KEY_DOCUMENT,
    KEY_PIPELINE_LOG,
    KEY_QUALITY_REPORT,
    KEY_REQUEST,
    KEY_SCORE,
    KEY_VALIDATION,
    ScoreValidationError,
    ScoreValidationStage,
    ValidationDiagnostic,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"


def _document(name: str, path: Path) -> MusicalDocument:
    return MusicalDocument(
        document_id=DocumentId(f"doc-{name}"),
        document_type=DocumentType.MUSICXML,
        path=path,
    )


def _acquisition(content: bytes, fmt: OutputFormat = OutputFormat.MUSICXML) -> AcquisitionResult:
    return AcquisitionResult(
        provider_id=ProviderId("omr"),
        source=MusicalSource(
            source_id=SourceId("src-1"),
            content=content,
            format=fmt,
            metadata={"title": "Test", "composer": "Composer"},
        ),
        confidence=Confidence(1.0),
        processing_time=Duration(0.0),
        format=fmt,
    )


def _context(content: bytes, document: MusicalDocument | None = None) -> PipelineContext:
    ctx = PipelineContext(data={KEY_ACQUISITION: _acquisition(content)})
    if document is not None:
        ctx = ctx.with_data(**{KEY_DOCUMENT: document})
        ctx = ctx.with_data(
            **{
                KEY_REQUEST: MusicalRequest(
                    request_id=RequestId("req-1"),
                    request_type=RequestType.MUSICXML,
                    document=document,
                )
            }
        )
    return ctx


def _score(ctx: PipelineContext) -> Score:
    score = ctx.data[KEY_SCORE]
    assert isinstance(score, Score)
    return score


def _report(ctx: PipelineContext) -> QualityReport:
    report = ctx.data[KEY_QUALITY_REPORT]
    assert isinstance(report, QualityReport)
    return report


def _diag(ctx: PipelineContext) -> ValidationDiagnostic:
    diag = ctx.data[KEY_VALIDATION]
    assert isinstance(diag, ValidationDiagnostic)
    return diag


def _log(ctx: PipelineContext) -> PipelineLog:
    log = ctx.data[KEY_PIPELINE_LOG]
    assert isinstance(log, PipelineLog)
    return log


def _run(context: PipelineContext) -> PipelineContext:
    return ScoreValidationStage().execute(context)


class TestValidMxl:
    def test_mxl_pequeno_valido(self) -> None:
        content = (FIXTURES / "real_short.mxl").read_bytes()
        ctx = _run(_context(content, _document("short", FIXTURES / "real_short.mxl")))

        score = _score(ctx)
        assert score.metadata["valid"] is True
        assert score.quality_level == QualityLevel.BASIC_MELODY

        diag = _diag(ctx)
        assert diag  # no ha fallado
        assert diag.errors == ()

    def test_mxl_grande_valido(self) -> None:
        content = (FIXTURES / "real_large.mxl").read_bytes()
        ctx = _run(_context(content, _document("large", FIXTURES / "real_large.mxl")))

        score = _score(ctx)
        assert score.metadata["valid"] is True
        assert score.metadata["parts"] == 7
        assert score.metadata["measures"] == 441
        warnings = score.metadata["warnings"]
        assert isinstance(warnings, list)
        assert "múltiples voces" in " ".join(warnings)

    def test_log_con_trazabilidad_completa(self) -> None:
        content = (FIXTURES / "real_short.mxl").read_bytes()
        doc = _document("short", FIXTURES / "real_short.mxl")
        ctx = _run(_context(content, doc))

        log = _log(ctx)
        assert log.request_id.value == "req-1"
        assert len(log.steps) == 1
        step = log.steps[0]
        assert step.step_name == "score_validation"
        assert step.success is True
        assert step.provider_id == ProviderId("omr")
        assert step.duration is not None
        assert step.timestamp is not None
        assert step.result is not None
        assert isinstance(step.result, dict)
        document_info = step.result["document"]
        assert isinstance(document_info, dict)
        assert document_info["document_id"] == "doc-short"
        assert document_info["document_type"] == "musicxml"
        assert step.result["quality_level"] == QualityLevel.BASIC_MELODY.value
        assert log.final_quality_level == QualityLevel.BASIC_MELODY


class TestDiagnosticos:
    def test_xml_mal_formado(self) -> None:
        with pytest.raises(ScoreValidationError):
            _run(_context(b"<score-partwise><part"))

    def test_xml_mal_formado_conserva_diagnostico(self) -> None:
        with pytest.raises(ScoreValidationError) as exc:
            _run(_context(b"<score-partwise><part"))
        assert exc.value.diagnostic is not None
        assert exc.value.diagnostic.failed is True
        assert exc.value.diagnostic.errors
        first_error = exc.value.diagnostic.errors[0]
        assert isinstance(first_error, str)
        assert "XML" in first_error or "validación" in first_error

    def test_estructura_incorrecta(self) -> None:
        with pytest.raises(ScoreValidationError) as exc:
            _run(_context(b"<foo/>"))
        assert exc.value.diagnostic is not None
        assert exc.value.diagnostic.failed is True

    def test_sin_notas(self) -> None:
        content = b"""<score-partwise version="3.1">
          <part-list><score-part id="P1"><part-name>P1</part-name></score-part></part-list>
          <part id="P1"><measure number="1"></measure></part>
        </score-partwise>"""
        with pytest.raises(ScoreValidationError) as exc:
            _run(_context(content))
        assert exc.value.diagnostic is not None
        assert exc.value.diagnostic.failed is True
        assert "notas" in " ".join(exc.value.diagnostic.errors)

    def test_contenido_invalido(self) -> None:
        content = b"""<score-partwise version="3.1">
          <part-list></part-list>
        </score-partwise>"""
        with pytest.raises(ScoreValidationError) as exc:
            _run(_context(content))
        assert exc.value.diagnostic is not None
        assert exc.value.diagnostic.failed is True
        assert exc.value.diagnostic.errors


class TestScoreConservaDiagnostico:
    def test_score_conserva_quality_report(self) -> None:
        """El Score del stage conserva exactamente el QualityReport del validador."""
        content = (FIXTURES / "real_short.mxl").read_bytes()
        acquisition = _acquisition(content)

        expected = BasicValidator().validate(acquisition)

        ctx = _run(PipelineContext(data={KEY_ACQUISITION: acquisition}))
        actual = _score(ctx)

        # calidad
        assert actual.quality_level == expected.quality_level
        # contenido sin alterar
        assert actual.content == expected.content
        # QualityReport idéntico (mismas dimensiones y valores)
        report_actual = _report(ctx)
        report_expected = expected.metadata["quality_report"]
        assert isinstance(report_expected, QualityReport)
        assert report_actual.dimensions == report_expected.dimensions
        # errores/warnings idénticos
        assert actual.metadata["errors"] == expected.metadata["errors"]
        assert actual.metadata["warnings"] == expected.metadata["warnings"]
        # campos estructurales idénticos
        for key in ("parts", "measures", "notes", "voices", "has_lyrics"):
            assert actual.metadata[key] == expected.metadata[key]

    def test_score_es_el_mismo_que_el_validador(self) -> None:
        """El Score del stage es funcionalmente equivalente al del validador directo."""
        content = (FIXTURES / "real_large.mxl").read_bytes()
        acquisition = _acquisition(content)

        expected = BasicValidator().validate(acquisition)
        ctx = _run(PipelineContext(data={KEY_ACQUISITION: acquisition}))
        actual = _score(ctx)

        assert actual.quality_level == expected.quality_level
        assert dict(actual.metadata) == dict(expected.metadata)
