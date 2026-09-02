"""Adquisición de una página de proveedor → `AcquiredPage`.

Cada proveedor entrega un `AcquiredPage` con las `ProviderWork` normalizadas (el contrato
v1.3) y la paginación (cursor siguiente, fin de proveedor o error). El resto de la
máquina (persistencia idempotente, progreso, límites) no depende de cómo responde un
proveedor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.osap.domain.search_request import SearchRequest
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    GenericProviderAdapter,
    ProviderQuery,
)
from src.osap.infrastructure.providers.contracts import (
    ProviderIdentity,
    ProviderLinks,
    ProviderMetadata,
    ProviderResource,
    ProviderStatistics,
    ProviderWork,
)

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation
    from src.osap.ports.catalog_provider import ICatalogProvider


@dataclass(frozen=True)
class AcquiredPage:
    provider: str
    cursor_value: str
    works: tuple[ProviderWork, ...] = ()
    next_cursor: str | None = None
    end_of_provider: bool = False
    error: str | None = None


class IProviderAcquirer(Protocol):
    """Adquiere una página de un proveedor dado un cursor opaco."""

    def acquire_page(self, provider: str, cursor_value: str, query: str) -> AcquiredPage:
        ...


class ProviderAdapterAcquirer:
    """Acquirer sobre el `GenericProviderAdapter` existente (nivel 1/2).

    El adapter actual devuelve todas las Works en una sola llamada (no expone metadatos de
    paginación), así que este acquirer entrega una única página y la marca como fin de
    proveedor (`end_of_provider`). Un proveedor realmente paginado aportaría su propio
    acquirer con `next_cursor`.
    """

    def __init__(self, provider_id: str, adapter: GenericProviderAdapter) -> None:
        self._provider_id = provider_id
        self._adapter = adapter

    def acquire_page(self, provider: str, cursor_value: str, query: str) -> AcquiredPage:
        try:
            page = int(cursor_value or "1") or 1
        except (TypeError, ValueError):
            page = 1
        works = self._adapter.search(ProviderQuery(query=query, page=page, limit=50))
        return AcquiredPage(
            provider=provider,
            cursor_value=cursor_value or "1",
            works=works,
            next_cursor=None,
            end_of_provider=True,
        )


class CatalogAcquirer:
    """Acquirer sobre un `ICatalogProvider` existente del catálogo.

    Reutiliza el provider ya wireado (RemoteCatalogProvider, LocalCatalogProvider, ...)
    sin duplicar su HTTP ni su mapping: delega en `provider.search(SearchRequest)` y
    convierte las `CandidateRepresentation` en el formato `ProviderWork.identity` que
    consume el universo/matcher. Entrega una única página (`end_of_provider`).
    """

    def __init__(self, provider_id: str, provider: ICatalogProvider) -> None:
        self._provider_id = provider_id
        self._provider = provider

    def acquire_page(self, provider: str, cursor_value: str, query: str) -> AcquiredPage:
        request = SearchRequest(query=query)
        try:
            candidates = self._provider.search(request)
        except Exception as exc:  # noqa: BLE001  # el error se registra como recuperable
            return AcquiredPage(provider=provider, cursor_value=cursor_value, error=str(exc))
        works = tuple(_candidate_to_provider_work(self._provider_id, c) for c in candidates)
        return AcquiredPage(
            provider=provider,
            cursor_value=cursor_value,
            works=works,
            next_cursor=None,
            end_of_provider=True,
        )


def _candidate_to_provider_work(provider_id: str, candidate: CandidateRepresentation) -> ProviderWork:
    """Convierte una CandidateRepresentation del catálogo a ProviderWork (contrato v1.3).

    El matcher consume `work.identity` con id/title/composer/catalogue/confidence; los
    recursos se usan como trazabilidad de representación (formato + URL de descarga).
    """
    desc = candidate.work_descriptor
    resources: list[ProviderResource] = []
    if candidate.download_url or candidate.view_url:
        resources.append(
            ProviderResource(
                id=candidate.remote_id or f"{candidate.candidate_id.value}",
                format=candidate.format.value,
                mime_type="",
                available=candidate.downloadable,
                license=candidate.license,
                links=ProviderLinks(
                    download=candidate.download_url,
                    view=candidate.view_url,
                    thumbnail=None,
                ),
            )
        )
    return ProviderWork(
        identity=ProviderIdentity(
            id=desc.work_id.value,
            title=desc.title,
            composer=desc.composer,
            catalogue=desc.catalogue_number,
            confidence=candidate.confidence.value,
        ),
        metadata=ProviderMetadata(
            subtitle=None,
            opus=None,
            musical_key=None,
            duration=None,
            measures=None,
            pages=None,
            parts=None,
            license=candidate.license,
            public_domain=candidate.public_domain,
            genres=(),
            tags=(),
            instruments=(),
        ),
        statistics=ProviderStatistics(favorites=0, downloads=0, views=0, rating=0.0),
        resources=tuple(resources),
    )


class FakePaginatedAcquirer:
    """Acquirer determinista y paginado para probar la máquina de adquisición.

    Produce `total_pages` páginas de `per_page` obras, con cursor numérico y
    `end_of_provider` en la última. Permite validar multi-página, idempotencia,
    reanudación y `complete`/`partial` sin depender de proveedores externos.
    """

    def __init__(
        self,
        total_pages: int = 10,
        per_page: int = 5,
        title_prefix: str = "Fake Work",
        fail_pages: set[int] | None = None,
    ) -> None:
        self._total_pages = total_pages
        self._per_page = per_page
        self._title_prefix = title_prefix
        self._fail_pages = fail_pages or set()
        self.calls: list[tuple[str, str, str]] = []

    def acquire_page(self, provider: str, cursor_value: str, query: str) -> AcquiredPage:
        self.calls.append((provider, cursor_value, query))
        try:
            page = int(cursor_value or "1")
        except (TypeError, ValueError):
            page = 1
        if page in self._fail_pages:
            return AcquiredPage(provider=provider, cursor_value=str(page), error="recoverable")
        if page > self._total_pages:
            return AcquiredPage(
                provider=provider,
                cursor_value=str(page),
                next_cursor=None,
                end_of_provider=True,
            )
        offset = (page - 1) * self._per_page
        works = tuple(
            _fake_work(offset + i, provider) for i in range(1, self._per_page + 1)
        )
        end = page >= self._total_pages
        return AcquiredPage(
            provider=provider,
            cursor_value=str(page),
            works=works,
            next_cursor=None if end else str(page + 1),
            end_of_provider=end,
        )


def _fake_work(index: int, provider: str) -> ProviderWork:
    return ProviderWork(
        identity=ProviderIdentity(
            id=f"{provider}-{index}",
            title=f"Fake Work {index}",
            composer="Fake Composer",
            confidence=0.9,
        )
    )


# --- serialización de ProviderWork → JSON (para provider_results.payload) ----------


def provider_work_to_dict(work: ProviderWork) -> dict[str, object]:
    identity = work.identity
    metadata = work.metadata
    stats = work.statistics
    return {
        "identity": {
            "id": identity.id,
            "title": identity.title,
            "composer": identity.composer,
            "catalogue": identity.catalogue,
            "confidence": identity.confidence,
        },
        "metadata": {
            "subtitle": metadata.subtitle,
            "opus": metadata.opus,
            "musical_key": metadata.musical_key,
            "duration": metadata.duration,
            "measures": metadata.measures,
            "pages": metadata.pages,
            "parts": metadata.parts,
            "license": metadata.license,
            "public_domain": metadata.public_domain,
            "genres": list(metadata.genres),
            "tags": list(metadata.tags),
            "instruments": list(metadata.instruments),
        },
        "statistics": {
            "favorites": stats.favorites,
            "downloads": stats.downloads,
            "views": stats.views,
            "rating": stats.rating,
        },
        "resources": [_resource_to_dict(r) for r in work.resources],
    }


def _resource_to_dict(resource: ProviderResource) -> dict[str, object]:
    links: ProviderLinks = resource.links
    return {
        "id": resource.id,
        "format": resource.format,
        "mime_type": resource.mime_type,
        "available": resource.available,
        "license": resource.license,
        "links": {
            "download": links.download,
            "view": links.view,
            "thumbnail": links.thumbnail,
        },
    }


def provider_works_to_json(works: tuple[ProviderWork, ...]) -> str:
    import json

    return json.dumps([provider_work_to_dict(w) for w in works], ensure_ascii=False)
