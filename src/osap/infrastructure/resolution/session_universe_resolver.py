"""SessionUniverseResolver — puente V2.1 para sesiones (F3.5, ADR-0035 D1).

Implementa la interfaz que consume `AcquisitionService.recompute_items`
(IUniverseMatcher: universe → resolution_items) con la pipeline canónica:

    provider_results (JSON, contrato de persistencia)
      → provider_work_from_dict  (vía de reanudación, sin HTTP)
      → domain_adapter           (CandidateRepresentation tipadas)
      → V21UniverseResolver      (Matcher → Ranker → Merge)
      → ResolutionDecisionPolicy (resolved | ambiguous | not_found)
      → resolution_serializer    (payload canónico determinista)

`SimpleUniverseMatcher`/`work_ranker.decide()` se conservan como referencia de paridad
hasta confirmar la retirada (no regresión sobre el corpus de las 250 obras).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.application.resolution_decision import (
    ResolutionCandidate,
    ResolutionDecisionPolicy,
)
from src.osap.application.universe_resolution import ResolvedGroup, V21UniverseResolver
from src.osap.domain.normalization import normalize_name
from src.osap.infrastructure.resolution.domain_adapter import provider_work_to_candidate
from src.osap.infrastructure.resolution.provider_acquirer import provider_work_from_dict
from src.osap.infrastructure.resolution.resolution_serializer import item_id, resolved_group_payload

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation


class SessionUniverseResolver:
    """Resuelve el universo de una sesión con la pipeline V2.1 y devuelve items."""

    def __init__(
        self,
        *,
        resolver: V21UniverseResolver | None = None,
        decision_policy: ResolutionDecisionPolicy | None = None,
    ) -> None:
        self._resolver = resolver or V21UniverseResolver()
        self._decision_policy = decision_policy or ResolutionDecisionPolicy()

    def match(self, universe: list[dict[str, object]]) -> list[dict[str, object]]:
        candidates = tuple(
            self._candidate_for(provider, work)
            for row in universe
            if isinstance((provider := row.get("provider")), str)
            if isinstance((work := row.get("work")), dict)
        )
        return self._items_for(candidates)

    def resolve_candidates(
        self,         candidates: tuple[CandidateRepresentation, ...]
    ) -> list[dict[str, object]]:
        """Igual que `match`, pero desde candidatos tipados (vía viva, sin JSON)."""
        return self._items_for(candidates)

    # --- helpers -------------------------------------------------------------

    @staticmethod
    def _candidate_for(provider: str, work: dict[str, object]) -> CandidateRepresentation:
        return provider_work_to_candidate(provider, provider_work_from_dict(work))

    def _items_for(self, candidates: tuple[CandidateRepresentation, ...]) -> list[dict[str, object]]:
        result = self._resolver.resolve(candidates)
        items: list[dict[str, object]] = []
        for group in result.groups:
            items.append(self._item_for(group))
        items.sort(key=lambda item: str(item["id"]))
        return items

    def _item_for(self, group: ResolvedGroup) -> dict[str, object]:
        payload = resolved_group_payload(group)
        composer = _group_composer(group)
        decision = self._decision_policy.decide(
            tuple(
                ResolutionCandidate(
                    provider=rep.provider_id.value,
                    confidence=rep.confidence.value,
                    composer=rep.work_descriptor.composer,
                )
                for rep in group.group.representations
            ),
            group_composer=composer,
        )
        return {
            "id": item_id(payload),
            "ref": payload["ref"],
            "status": decision.status,
            "normalized": payload["normalized"],
            "resolved": payload["resolved"],
            "confidence": payload["confidence"],
            "candidates": payload["candidates"],
            "evidence": payload["evidence"],
        }


def _group_composer(group: ResolvedGroup) -> str | None:
    """Atribución consolidada del grupo: un único compositor distinto normalizado.

    Nunca inventa `Anonymous/Traditional` (ADR-0034): si no hay acuerdo entre los
    miembros (o ninguno aporta compositor), devuelve None.
    """
    seen: dict[str, str] = {}
    for rep in group.group.representations:
        composer = rep.work_descriptor.composer
        if not composer:
            continue
        key = normalize_name(composer)
        seen.setdefault(key, composer)
    if len(seen) == 1:
        return next(iter(seen.values()))
    return None


__all__ = ["SessionUniverseResolver"]
