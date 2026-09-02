"""Adaptadores entre el `Score` de OSAP y el `ScoreContract` serializable.

La frontera OSAP → Chorus es el contrato (datos), no clases Python. Estos adaptadores
mapean en ambos sentidos y mantienen la dependencia de OSAP LOCALIZADA: los imports de
OSAP son lazy, dentro de cada función, para que `import src.chorus.contract` no cargue
módulos de OSAP.

Decisiones de pérdida consciente (no silenciosa):
- `content` (bytes de la obra original) NO forma parte del contrato: Chorus no lo usa
  hoy y es el payload pesado. Al reconstruir el Score se usa un marcador vacío.
- `score_id` interno de OSAP NO se transporta: al reconstruir se genera un id marcador.
- `valid` se deriva de `quality.level > 0` al reconstruir (no se serializa).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.chorus.contract.model import Diagnostics, Quality, ScoreContract, Structure

if TYPE_CHECKING:
    from src.osap.domain.score import Score

_MARKER_CONTENT = b""
_MARKER_SCORE_ID = "contract-score"


def score_to_contract(score: Score) -> ScoreContract:
    """Serializa un `Score` real de OSAP al contrato (datos mínimos que usa Chorus)."""
    metadata = score.metadata
    report = metadata.get("quality_report")
    if isinstance(report, dict):
        quality_report: dict[str, float] = {
            str(key): float(value) for key, value in report.items()
        }
    else:
        dimensions = getattr(report, "dimensions", {})
        quality_report = {
            str(getattr(dimension, "value", str(dimension))): float(value)
            for dimension, value in dimensions.items()
        }
    return ScoreContract(
        schema_version=1,
        title=score.title,
        composer=score.composer,
        structure=Structure(
            parts=_optional_int(metadata.get("parts")),
            measures=_optional_int(metadata.get("measures")),
            notes=_optional_int(metadata.get("notes")),
            voices=_optional_int(metadata.get("voices")),
            has_lyrics=_optional_bool(metadata.get("has_lyrics")),
        ),
        quality=Quality(
            level=score.quality_level.value,
            report=quality_report,
        ),
        diagnostics=Diagnostics(
            errors=_string_list(metadata.get("errors")),
            warnings=_string_list(metadata.get("warnings")),
        ),
    )


def contract_to_score(contract: ScoreContract) -> Score:
    """Reconstruye un `Score` de OSAP desde el contrato (equivalente para Chorus)."""
    if contract.quality is None or contract.structure is None:
        raise ValueError("El contrato debe incluir structure y quality.")

    from src.osap.domain.quality_level import QualityLevel
    from src.osap.domain.quality_report import QualityDimension, QualityReport
    from src.osap.domain.score import Score
    from src.osap.domain.value_objects import ScoreId

    structure = contract.structure
    quality = contract.quality
    diagnostics = contract.diagnostics or Diagnostics()
    quality_report = QualityReport(
        {
            QualityDimension(name): float(score)
            for name, score in quality.report.items()
            if _is_known_dimension(name)
        }
    )
    return Score(
        score_id=ScoreId(_MARKER_SCORE_ID),
        content=_MARKER_CONTENT,
        title=contract.title,
        composer=contract.composer,
        quality_level=QualityLevel(quality.level),
        metadata={
            "valid": quality.level > 0,
            "errors": list(diagnostics.errors),
            "warnings": list(diagnostics.warnings),
            "parts": structure.parts,
            "measures": structure.measures,
            "notes": structure.notes,
            "voices": structure.voices,
            "has_lyrics": structure.has_lyrics,
            "quality_report": quality_report,
        },
    )


def _is_known_dimension(name: str) -> bool:
    from src.osap.domain.quality_report import QualityDimension

    return name in {dimension.value for dimension in QualityDimension}


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]
