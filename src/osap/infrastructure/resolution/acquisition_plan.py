"""Plan de adquisición de una ResolutionSession.

Determina proveedores activos, tipo de paginación de cada proveedor, cursor inicial y
aplica los límites de política (`max_pages_per_provider`, `max_results_to_acquire`,
`max_duration_s`). No decide qué obra es mejor: eso es el matching (FASE 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from src.osap.infrastructure.resolution.provider_acquirer import (
    FakePaginatedAcquirer,
    IProviderAcquirer,
)

DEFAULT_PAGINATION_KIND = "page"
DEFAULT_INITIAL_CURSOR = "1"

_PAGINATION_KINDS: dict[str, str] = {}


@dataclass(frozen=True)
class AcquisitionPlan:
    providers: tuple[str, ...]
    pagination_kinds: dict[str, str] = field(default_factory=dict)
    initial_cursors: dict[str, str] = field(default_factory=dict)
    max_pages_per_provider: int = 20
    max_results_to_acquire: int = 500
    max_duration_s: int = 120
    max_recoverable_retries: int = 2

    def pagination_kind(self, provider: str) -> str:
        return self.pagination_kinds.get(provider, DEFAULT_PAGINATION_KIND)

    def initial_cursor(self, provider: str) -> str:
        return self.initial_cursors.get(provider, DEFAULT_INITIAL_CURSOR)


def _pagination_kind_for(provider: str, acquirers: dict[str, IProviderAcquirer] | None) -> str:
    if _PAGINATION_KINDS.get(provider):
        return _PAGINATION_KINDS[provider]
    if acquirers and isinstance(acquirers.get(provider), FakePaginatedAcquirer):
        return "cursor"
    return DEFAULT_PAGINATION_KIND


def build_acquisition_plan(
    providers: list[str],
    policy: dict[str, object],
    acquirers: dict[str, IProviderAcquirer] | None = None,
) -> AcquisitionPlan:
    """Construye el plan a partir de los proveedores de la sesión y su política."""
    policy = policy or {}
    kinds: dict[str, str] = {}
    cursors: dict[str, str] = {}
    for provider in providers:
        kinds[provider] = _pagination_kind_for(provider, acquirers)
        cursors[provider] = _PAGINATION_KINDS.get(provider, DEFAULT_INITIAL_CURSOR)
    return AcquisitionPlan(
        providers=tuple(providers),
        pagination_kinds=kinds,
        initial_cursors=cursors,
        max_pages_per_provider=int(cast("int", policy.get("max_pages_per_provider") or 20)),
        max_results_to_acquire=int(cast("int", policy.get("max_results_to_acquire") or 500)),
        max_duration_s=int(cast("int", policy.get("max_duration_s") or 120)),
        max_recoverable_retries=int(cast("int", policy.get("max_recoverable_retries") or 2)),
    )
