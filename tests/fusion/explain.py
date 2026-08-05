"""Explain: ¿por qué?

Renderiza la cadena de evidencias de una decisión (MergeDecision) y los
campos normalizados (RepresentationIdentity), para depurar en minutos por qué
dos representaciones se fusionan o no.
"""

from __future__ import annotations

from normalizer import RepresentationIdentity, build_identity
from src.osap.application.work_grouping_matcher import MergeDecision


def explain_decision(decision: MergeDecision) -> list[str]:
    """Líneas legibles que explican una decisión."""
    lines = [f"score={decision.score:.2f} decision={decision.decision.value}"]
    for label, value in decision.breakdown:
        lines.append(f"  {label:<10} {('—' if value is None else f'{value:.2f}')}")
    lines.append("  evidence: " + (", ".join(e.label for e in decision.evidence) or "—"))
    return lines


def identity_fields(title: str, composer: str | None) -> RepresentationIdentity:
    """Ficha de identidad de una representación (7 campos normalizados)."""
    return build_identity(title, composer)
