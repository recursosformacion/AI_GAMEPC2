"""RISM leído desde el índice local de osap-storage (no desde opac.rism.info).

osap-storage mantiene un corpus RISM propio (`rism_sources`) y lo expone en
`/api/search?corpus=rism`. Este provider consume ese endpoint: la búsqueda de RISM la hace
storage (su índice) y osap-api no reindexa nada.

RISM es **metadata/fuente**: no aporta fichero de partitura (sin descarga), pero sí
compositor, título uniforme, signatura e institución para localizar la fuente.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests

from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    ProviderId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.http.browser_headers import browser_headers
from src.osap.ports.catalog_provider import ICatalogProvider

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.resolve_request import ResolveRequest
    from src.osap.domain.search_request import SearchRequest

logger = logging.getLogger("osap.rism")


class RismStorageCatalogProvider(ICatalogProvider):
    """Búsqueda RISM contra el corpus local expuesto por osap-storage."""

    def __init__(
        self,
        base_url: str = "https://storage.openmusicrepository.com",
        timeout: int = 10,
        token_provider: Callable[[], str] | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._token_provider = token_provider

    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("rism")

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            # RISM se sirve desde osap-storage (red): NO es offline. Si se marcara offline,
            # el enriquecimiento por obra (`online(False)`) lo consultaría por cada resultado.
            offline=False,
            formats=(),
            public_domain_only=False,
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("rism"),
            name="RISM",
            provider_id=self.provider_id,
            source="https://opac.rism.info",
            status=CatalogStatus.INSTALLED,
        )

    # -- búsqueda --------------------------------------------------------------

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        q = (request.query or request.title or request.composer or "").strip()
        if not q:
            return ()
        headers = browser_headers({"Accept": "application/json"})
        if self._token_provider is not None:
            try:
                token = self._token_provider()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
            except Exception:  # noqa: BLE001 — sin token se intenta acceso público
                pass
        try:
            resp = requests.get(
                f"{self._base}/api/search",
                params={"q": q, "corpus": "rism", "limit": "50"},
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 — RISM nunca debe tumbar la búsqueda
            logger.warning("RISM (storage) no disponible: %s", exc)
            return ()
        rows = payload.get("rism_sources") if isinstance(payload, dict) else None
        out: list[CandidateRepresentation] = []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                candidate = self._to_candidate(row)
                if candidate is not None:
                    out.append(candidate)
        return tuple(out)

    def _to_candidate(self, row: dict[str, object]) -> CandidateRepresentation | None:
        source_id = str(row.get("source_id") or "")
        if not source_id:
            return None
        uniform = str(row.get("uniform_title") or "").strip()
        raw_title = str(row.get("title") or "").strip()
        title = uniform or raw_title[:200] or source_id
        view_url = ""
        links = row.get("links")
        if isinstance(links, list) and links:
            first = links[0]
            if isinstance(first, dict):
                view_url = str(first.get("url") or "")
            elif isinstance(first, str):
                view_url = first
        if not view_url and source_id:
            # Fallback: permalink de la ficha RISM derivado del `source_id`
            # ('sources/455010113' -> https://rism.online/sources/455010113). Muchas fuentes
            # no traen copia digitalizada (`links: []`); así siempre hay "abrir en RISM".
            view_url = "https://rism.online/" + source_id.lstrip("/")
        metadata: dict[str, object] = {
            "rism_source_id": source_id,
            "shelfmark": row.get("shelfmark"),
            "source_type": row.get("source_type"),
            "institution_id": row.get("institution_id"),
            "language": row.get("language"),
            "has_incipit": row.get("has_incipit"),
        }
        work = WorkDescriptor(
            work_id=WorkId(f"rism:{source_id}"),
            title=title,
            composer=str(row.get("composer_name") or None) or None,
            metadata=metadata,
        )
        return CandidateRepresentation(
            candidate_id=CandidateId(f"rism:{source_id}"),
            work_descriptor=work,
            provider_id=self.provider_id,
            format=OutputFormat.PDF,
            origin="rism",
            public_domain=True,
            # RISM es una fuente (metadata): no hay notación utilizable que descargar.
            quality=QualityLevel.UNREADABLE,
            confidence=Confidence(0.4),
            download_url=None,
            view_url=view_url or None,
            downloadable=False,
            manual_download=False,
            remote_id=source_id,
            metadata=metadata,
        )

    # -- circuitos NO usados por esta integración -------------------------------

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        raise NotImplementedError("RISM no participa en resolve: la búsqueda es por catálogo")

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        raise NotImplementedError("RISM no ofrece descarga: es metadata de fuentes")
