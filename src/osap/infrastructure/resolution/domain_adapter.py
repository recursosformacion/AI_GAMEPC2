"""Adaptador sesión/provider_results → objetos de dominio (F3, ADR-0035 D1).

Reconstruye ``CandidateRepresentation``/``WorkDescriptor`` desde el contrato v1.3
(``ProviderWork``) para alimentar la pipeline V2.1 canónica. Reglas:

- **Solo reconstruye**: nunca decide identidad ni estado, nunca agrupa.
- **No inventa datos ausentes** (ADR-0034): ``composer=None`` se conserva como desconocido
  (nunca Anonymous/Traditional); quality/completeness/checksum no se fabrican; sin recursos
  → representación no descargable con el formato por defecto.
- La vía de reanudación (``provider_results`` JSON) es un subconjunto documentado y con
  pérdida; la vía viva (adquirida en el mismo proceso) conserva los objetos originales.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

if TYPE_CHECKING:
    from src.osap.infrastructure.providers.contracts import ProviderResource, ProviderWork

_FORMAT_PREFERENCE = {
    "musicxml": 0,
    "mei": 1,
    "midi": 2,
    "pdf": 3,
    "json": 4,
    "score": 5,
}


def provider_works_to_candidates(
    provider: str, works: tuple[ProviderWork, ...]
) -> tuple[CandidateRepresentation, ...]:
    """Convierte un lote de ProviderWork en representaciones de dominio (una por obra)."""
    return tuple(provider_work_to_candidate(provider, work) for work in works)


def provider_work_to_candidate(provider: str, work: ProviderWork) -> CandidateRepresentation:
    """Convierte una ProviderWork en la CandidateRepresentation de dominio.

    Elige el mejor recurso disponible (MusicXML > MEI > MIDI > PDF > …) para el formato y
    los enlaces de descarga. Si la obra no trae recursos, se emite una representación no
    descargable para conservar la evidencia de que el proveedor anunció la obra.
    """
    identity = work.identity
    metadata = work.metadata
    resource = _best_resource(work.resources)
    resource_id = resource.id if resource is not None else identity.id
    downloadable = bool(
        resource is not None and (resource.available or bool(resource.links.download))
    )
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{provider}:{resource_id}"),
        work_descriptor=WorkDescriptor(
            work_id=WorkId(identity.id or f"{provider}:{resource_id}"),
            title=identity.title,
            subtitle=metadata.subtitle,
            composer=identity.composer,
            opus=metadata.opus,
            catalogue_number=identity.catalogue,
            key=metadata.musical_key,
            genres=tuple(str(genre) for genre in metadata.genres),
            instrumentation=tuple(str(instrument) for instrument in metadata.instruments),
        ),
        provider_id=ProviderId(provider),
        format=_resource_format(resource),
        license=(resource.license if resource is not None else None) or metadata.license,
        public_domain=metadata.public_domain,
        confidence=Confidence(identity.confidence),
        # quality/completeness/checksum no son expresables en ProviderWork hoy: valores
        # por defecto honestos, nunca inventados (ver v21-session-bridge-design.md §2).
        downloadable=downloadable,
        download_url=resource.links.download if resource is not None else None,
        view_url=resource.links.view if resource is not None else None,
        remote_id=identity.id,
    )


def _best_resource(resources: tuple[ProviderResource, ...]) -> ProviderResource | None:
    if not resources:
        return None
    return min(
        resources,
        key=lambda r: (
            _FORMAT_PREFERENCE.get((r.format or "").lower(), 99),
            r.id or "",
        ),
    )


def _resource_format(resource: ProviderResource | None) -> OutputFormat:
    if resource is None:
        return OutputFormat.PDF
    try:
        return OutputFormat((resource.format or "").lower())
    except ValueError:
        return OutputFormat.PDF
