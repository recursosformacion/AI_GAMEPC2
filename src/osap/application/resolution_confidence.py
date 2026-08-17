"""resolution_confidence — confianza continua de una resolución de obra (FASE 5.8).

Separa identidad de obra y atribución de compositor en señales, y produce un valor 0..1
en lugar de un binario resolved/ambiguous. Cada señal es evidencia trazable (no una
fórmula ciega): se suman componentes que el equipo puede ponderar con datos.

Componentes (cada uno opcional, con su razón):
  * identidad: obra recuperada (+0.2), wikidata_work (+0.15), varios proveedores (+0.10)
  * atribución: compositor encontrado (+0.25), procedente de campo del proveedor (+0.10)
  * validación: compositor confirmado por autoridad (ISNI/VIAF) (+0.30)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfidenceBreakdown:
    identity: float
    attribution: float
    validation: float
    total: float
    reasons: list[str] = field(default_factory=list)


def resolution_confidence(
    *,
    recovered: bool,
    wikidata_work: bool,
    provider_count: int,
    composer_found: bool,
    composer_from_field: bool,
    composer_validated: bool,
) -> ConfidenceBreakdown:
    reasons: list[str] = []
    identity = 0.0
    if recovered:
        identity += 0.2
        reasons.append("obra recuperada")
    if wikidata_work:
        identity += 0.15
        reasons.append("wikidata_work")
    if provider_count >= 2:
        identity += 0.10
        reasons.append(f"{provider_count} proveedores")

    attribution = 0.0
    if composer_found:
        attribution += 0.25
        reasons.append("compositor encontrado")
        if composer_from_field:
            attribution += 0.10
            reasons.append("atribución de campo del proveedor")

    validation = 0.30 if composer_validated else 0.0
    if composer_validated:
        reasons.append("validado por autoridad (ISNI/VIAF)")

    total = round(min(1.0, identity + attribution + validation), 3)
    return ConfidenceBreakdown(
        identity=round(identity, 3),
        attribution=round(attribution, 3),
        validation=validation,
        total=total,
        reasons=reasons,
    )


def classify(total: float) -> str:
    """Etiqueta orientativa desde la confianza (revisable con datos)."""
    if total >= 0.8:
        return "resolved"
    if total >= 0.55:
        return "resolved_candidate"  # compositor encontrado, sin validar
    return "ambiguous"
