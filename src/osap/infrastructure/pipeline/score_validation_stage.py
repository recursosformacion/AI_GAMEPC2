"""Stage de validación del Score Acquisition Pipeline.

Recibe un `MusicalDocument` (vía `MusicalRequest`) y un `AcquisitionResult`
(MusicXML/.mxl) desde el `PipelineContext.data`, ejecuta el `BasicValidator`
(validación MusicXML por niveles) y produce:

  * `Score` — con el contenido MusicXML, `QualityReport` y `QualityLevel`;
  * `PipelineLog` — trazabilidad (documento, fuente, resultado, errores,
    warnings, nivel de calidad, timestamps);
  * un `PipelineStep` en el log.

Si el MusicXML es inválido, el pipeline falla de forma controlada: el stage
lanza `ScoreValidationError` pero conserva el diagnóstico en `data` y en el
`PipelineLog` para auditoría.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.osap.domain.pipeline_log import PipelineLog, PipelineStep
from src.osap.domain.value_objects import Duration, RequestId
from src.osap.ports.pipeline_stage import IPipelineStage

if TYPE_CHECKING:
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.musical_document import MusicalDocument
    from src.osap.domain.pipeline_context import PipelineContext
    from src.osap.domain.quality_level import QualityLevel
    from src.osap.domain.quality_report import QualityReport
    from src.osap.domain.score import Score
    from src.osap.ports.score_validator import IScoreValidator


class ScoreValidationError(Exception):
    """El MusicXML no es utilizable; el pipeline falla de forma controlada.

    Transporta el `ValidationDiagnostic` para que el llamante conserve toda la
    información de trazabilidad (score, report, log, errores, warnings).
    """

    def __init__(self, message: str, diagnostic: ValidationDiagnostic | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class ValidationDiagnostic:
    """Diagnóstico conservado aunque el stage falle (para trazabilidad)."""

    score: Score | None = None
    report: QualityReport | None = None
    log: PipelineLog | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    failed: bool = False

    def __bool__(self) -> bool:
        return not self.failed


# Claves usadas en PipelineContext.data.
KEY_REQUEST = "musical_request"
KEY_DOCUMENT = "musical_document"
KEY_ACQUISITION = "acquisition_result"
KEY_SCORE = "score"
KEY_QUALITY_REPORT = "quality_report"
KEY_PIPELINE_LOG = "pipeline_log"
KEY_VALIDATION = "validation_diagnostic"


class ScoreValidationStage(IPipelineStage):
    """Valida la representación musical adquirida y produce el `Score` fiable."""

    def __init__(self, validator: IScoreValidator | None = None) -> None:
        from src.osap.infrastructure.adapters.validation import BasicValidator

        self._validator: IScoreValidator = validator or BasicValidator()

    @property
    def name(self) -> str:
        return "score_validation"

    def execute(self, context: PipelineContext) -> PipelineContext:
        started = time.monotonic()
        timestamp = datetime.now(UTC)

        acquisition = context.data.get(KEY_ACQUISITION)
        document = context.data.get(KEY_DOCUMENT)
        request = context.data.get(KEY_REQUEST)

        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(acquisition, _acquisition_type()):
            raise ScoreValidationError("falta acquisition_result en el contexto del pipeline")
        if document is not None and not isinstance(document, _document_type()):
            raise ScoreValidationError("musical_document del contexto no es un MusicalDocument")

        request_id = _request_id_of(request)

        try:
            score = self._validator.validate(acquisition)
        except Exception as exc:  # noqa: BLE001  # el diagnóstico se conserva
            errors.append(f"validación falló: {exc}")
            log = self._build_log(request_id, document, acquisition, errors, warnings, None, started, timestamp)
            diagnostic = ValidationDiagnostic(
                errors=tuple(errors), warnings=tuple(warnings), failed=True,
            )
            context = context.with_data(
                **{
                    KEY_VALIDATION: diagnostic,
                    KEY_PIPELINE_LOG: log,
                }
            )
            raise ScoreValidationError("; ".join(errors), diagnostic) from exc

        quality_report: QualityReport | None
        raw_report = score.metadata.get("quality_report")
        if isinstance(raw_report, _quality_report_type()):
            quality_report = raw_report
        else:
            errors.append("el validador no produjo QualityReport")
            quality_report = None

        raw_errors = score.metadata.get("errors", ())
        raw_warnings = score.metadata.get("warnings", ())
        if isinstance(raw_errors, (list, tuple)):
            errors.extend(str(e) for e in raw_errors)
        if isinstance(raw_warnings, (list, tuple)):
            warnings.extend(str(w) for w in raw_warnings)
        usable = bool(score.metadata.get("valid", False)) and not errors
        log = self._build_log(request_id, document, acquisition, errors, warnings, score, started, timestamp)
        diagnostic = ValidationDiagnostic(
            score=score,
            report=quality_report,
            log=log,
            errors=tuple(errors),
            warnings=tuple(warnings),
            failed=not usable,
        )

        context = context.with_data(
            **{
                KEY_SCORE: score,
                KEY_QUALITY_REPORT: quality_report,
                KEY_PIPELINE_LOG: log,
                KEY_VALIDATION: diagnostic,
            }
        )

        if not usable:
            raise ScoreValidationError("; ".join(errors) or "MusicXML no utilizable", diagnostic)
        return context

    def _build_log(
        self,
        request_id: RequestId,
        document: MusicalDocument | None,
        acquisition: AcquisitionResult,
        errors: list[str],
        warnings: list[str],
        score: Score | None,
        started: float,
        timestamp: datetime,
    ) -> PipelineLog:
        duration = Duration(round(time.monotonic() - started, 4))
        document_info = None
        if document is not None:
            document_info = {
                "document_id": document.document_id.value,
                "document_type": document.document_type.value,
            }
        step_result = (
            {
                "document": document_info,
                "errors": errors,
                "warnings": warnings,
                "quality_level": score.quality_level.value,
            }
            if score
            else {"document": document_info, "errors": errors, "warnings": warnings}
        )
        step = PipelineStep(
            step_name=self.name,
            provider_id=acquisition.provider_id,
            result=step_result,
            success=bool(score and not errors),
            duration=duration,
            timestamp=timestamp,
        )
        return PipelineLog(
            request_id=request_id,
            steps=(step,),
            selected_provider_id=acquisition.provider_id,
            final_quality_level=score.quality_level if score else _unreadable(),
            output_format=acquisition.format,
            created_at=timestamp,
        )


def _request_id_of(request: object) -> RequestId:
    if request is not None:
        rid = getattr(request, "request_id", None)
        if rid is not None:
            return RequestId(str(rid.value) if hasattr(rid, "value") else str(rid))
    return RequestId(f"pipeline-{int(time.time() * 1000)}")


def _unreadable() -> QualityLevel:
    from src.osap.domain.quality_level import QualityLevel

    return QualityLevel.UNREADABLE


def _acquisition_type() -> type[AcquisitionResult]:
    from src.osap.domain.acquisition_result import AcquisitionResult

    return AcquisitionResult


def _document_type() -> type[MusicalDocument]:
    from src.osap.domain.musical_document import MusicalDocument

    return MusicalDocument


def _quality_report_type() -> type[QualityReport]:
    from src.osap.domain.quality_report import QualityReport

    return QualityReport
