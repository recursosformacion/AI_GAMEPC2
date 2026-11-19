"""Modelos del subsistema de enriquecimiento multifuente."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class EnrichmentCandidate:
    """Un valor propuesto para un campo, con su procedencia y confianza."""

    entity_type: str  # "person" | "work"
    entity_key: str
    field: str
    value: str
    source: str
    evidence_url: str
    confidence: float
    license: str = ""
    fetched_at: str = ""

    def with_fetched_at(self, stamp: str) -> EnrichmentCandidate:
        return replace(self, fetched_at=stamp)
