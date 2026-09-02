"""Contrato serializable mínimo de `Score` (frontera OSAP → Chorus).

Define qué información necesita Chorus para recibir una obra ya validada y
estructurada (un `Score`), de forma independiente de las clases Python de OSAP.

El contrato representa una obra ya validada, lista para `GenerateMaterialsUseCase`;
NO representa búsqueda ni adquisición. Contiene únicamente los datos que usa hoy
Chorus (`ExerciseGenerator`): identidad, estructura, calidad y diagnósticos.

Este módulo NO importa OSAP: el contrato se expresa como datos (dict/JSON) y es
independiente del lenguaje. Versionado mínimo mediante `schema_version`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

CONTRACT_SCHEMA_VERSION = 1

# Niveles de calidad del contrato (equivalentes a QualityLevel de OSAP: 0=ilegible).
_UNREADABLE_LEVEL = 0
_MAX_QUALITY_LEVEL = 4


class ContractError(ValueError):
    """Contrato inválido o incompatible (mensaje seguro, sin internals)."""


@dataclass(frozen=True)
class Structure:
    """Estructura musical real de la obra (lo que Chorus usa para materiales)."""

    parts: int | None = None
    measures: int | None = None
    notes: int | None = None
    voices: int | None = None
    has_lyrics: bool | None = None


@dataclass(frozen=True)
class Quality:
    """Calidad de la obra: nivel + dimensiones del QualityReport."""

    level: int
    report: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Diagnostics:
    """Errores y warnings asociados a la validación de la obra."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreContract:
    """Documento serializable que transporta un `Score` válido hacia Chorus."""

    schema_version: int = CONTRACT_SCHEMA_VERSION
    title: str | None = None
    composer: str | None = None
    structure: Structure | None = None
    quality: Quality | None = None
    diagnostics: Diagnostics | None = None

    # ------------------------------------------------------------------ output

    def to_dict(self) -> dict[str, object]:
        doc: dict[str, object] = {
            "schema_version": self.schema_version,
            "title": self.title,
            "composer": self.composer,
        }
        if self.structure is not None:
            doc["structure"] = {
                "parts": self.structure.parts,
                "measures": self.structure.measures,
                "notes": self.structure.notes,
                "voices": self.structure.voices,
                "has_lyrics": self.structure.has_lyrics,
            }
        if self.quality is not None:
            doc["quality"] = {
                "level": self.quality.level,
                "report": dict(self.quality.report),
            }
        if self.diagnostics is not None:
            doc["diagnostics"] = {
                "errors": list(self.diagnostics.errors),
                "warnings": list(self.diagnostics.warnings),
            }
        return doc

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    # ------------------------------------------------------------------ input

    @classmethod
    def from_dict(cls, doc: object) -> ScoreContract:
        if not isinstance(doc, dict):
            raise ContractError("El contrato debe ser un objeto JSON.")
        version = doc.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise ContractError("El contrato debe incluir un schema_version.")
        if version != CONTRACT_SCHEMA_VERSION:
            raise ContractError(f"schema_version {version} no soportada.")
        title = _optional_str(doc.get("title"), "title")
        composer = _optional_str(doc.get("composer"), "composer")
        structure = _parse_structure(doc.get("structure"))
        quality = _parse_quality(doc.get("quality"))
        diagnostics = _parse_diagnostics(doc.get("diagnostics"))
        if structure is None or quality is None:
            raise ContractError("El contrato debe incluir structure y quality.")
        return cls(
            schema_version=version,
            title=title,
            composer=composer,
            structure=structure,
            quality=quality,
            diagnostics=diagnostics,
        )

    @classmethod
    def from_json(cls, text: str) -> ScoreContract:
        try:
            doc = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise ContractError("El contrato no es un JSON válido.") from exc
        return cls.from_dict(doc)


def _parse_structure(value: object) -> Structure | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ContractError("structure debe ser un objeto.")
    return Structure(
        parts=_optional_int(value.get("parts"), "structure.parts"),
        measures=_optional_int(value.get("measures"), "structure.measures"),
        notes=_optional_int(value.get("notes"), "structure.notes"),
        voices=_optional_int(value.get("voices"), "structure.voices"),
        has_lyrics=_optional_bool(value.get("has_lyrics"), "structure.has_lyrics"),
    )


def _parse_quality(value: object) -> Quality | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ContractError("quality debe ser un objeto.")
    level = value.get("level")
    if not isinstance(level, int) or isinstance(level, bool):
        raise ContractError("quality.level debe ser un entero.")
    if not 0 <= level <= _MAX_QUALITY_LEVEL:
        raise ContractError("quality.level está fuera de rango.")
    report = value.get("report", {})
    if not isinstance(report, dict):
        raise ContractError("quality.report debe ser un objeto.")
    parsed_report: dict[str, float] = {}
    for key, raw in report.items():
        if not isinstance(key, str) or isinstance(raw, bool):
            raise ContractError("quality.report contiene valores inválidos.")
        try:
            score = float(raw)
        except (TypeError, ValueError) as exc:
            raise ContractError("quality.report contiene valores inválidos.") from exc
        if not 0.0 <= score <= 1.0:
            raise ContractError("quality.report contiene puntuaciones fuera de [0, 1].")
        parsed_report[key] = score
    return Quality(level=level, report=parsed_report)


def _parse_diagnostics(value: object) -> Diagnostics | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ContractError("diagnostics debe ser un objeto.")
    return Diagnostics(
        errors=_string_list(value.get("errors"), "diagnostics.errors"),
        warnings=_string_list(value.get("warnings"), "diagnostics.warnings"),
    )


def _optional_str(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractError(f"{name} debe ser texto.")
    return value


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractError(f"{name} debe ser un entero.")
    return value


def _optional_bool(value: object, name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ContractError(f"{name} debe ser booleano.")
    return value


def _string_list(value: object, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractError(f"{name} debe ser una lista de textos.")
    return list(value)


def is_readable_contract(contract: ScoreContract) -> bool:
    """True si el contrato representa una obra legible (nivel > ilegible)."""
    return contract.quality is not None and contract.quality.level > _UNREADABLE_LEVEL
