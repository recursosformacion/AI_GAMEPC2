"""Catálogo CPDL (corpus independiente en osap-storage).

Arquitectura acordada:
    cpdl_pages  ->  cpdl_voicings  ->  CPDLCatalogProvider.search  ->  buscador general
    ->  resultados CPDL  ->  fusión LÓGICA con Works

El proveedor consulta el endpoint de SOLO LECTURA de osap-storage
(`/api/v1/cpdl/search`); nunca lee la BD de storage directamente ni toca `works`.
`voicing` es un criterio descriptivo (token normalizado exacto, case-insensitive):
los términos viajan en `SearchRequest.voices`. Los providers sin soporte lo ignoran.
Cada página CPDL sigue siendo UN registro, aunque contenga varios voicings.

NO se reutiliza `resolve()` para buscar y NO se introducen representaciones
descargables artificiales: cada resultado es la página CPDL (enlace wiki).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

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


class CPDLCatalogProvider(ICatalogProvider):
    """Provider CPDL basado en el corpus de páginas de osap-storage."""

    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], str | None] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token_provider = token_provider
        self._timeout = timeout

    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("cpdl")

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            offline=True,
            formats=(OutputFormat.MUSICXML, OutputFormat.PDF),
            public_domain_only=False,
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("cpdl"),
            name="CPDL",
            provider_id=self.provider_id,
            source="https://www.cpdl.org",
            status=CatalogStatus.INSTALLED,
        )

    # -- búsqueda --------------------------------------------------------------

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        voices = list(
            dict.fromkeys(v.strip() for v in (request.voices or ()) if v and v.strip())
        )
        q = (request.query or request.title or request.composer or "").strip()
        if not voices and not q:
            return ()

        params: list[tuple[str, str]] = [(("voicing", v)) for v in voices]
        if q:
            params.append(("q", q))
        url = f"{self._base}/api/v1/cpdl/search"
        headers = browser_headers({"Accept": "application/json"})
        token: str | None = None
        if self._token_provider is not None:
            try:
                token = self._token_provider()
            except Exception:  # noqa: BLE001 — sin token se intenta en acceso público
                token = None
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = requests.get(url, params=params, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        rows = resp.json() if isinstance(resp.json(), list) else []

        out: list[CandidateRepresentation] = []
        for row in rows:
            rep = self._to_candidate(row)
            if rep is not None:
                out.append(rep)
        return tuple(out)

    def _to_candidate(self, row: dict[str, object]) -> CandidateRepresentation | None:
        page_title = str(row.get("page_title") or "")
        if not page_title:
            return None
        page_id = row.get("id")
        raw_terms = row.get("voicing_terms")
        terms: list[str] = []
        if isinstance(raw_terms, list):
            terms = [str(t) for t in raw_terms if isinstance(t, str)]
        page_url = str(row.get("page_url") or "")
        if not page_url:
            page_url = (
                "https://www.cpdl.org/wiki/index.php?title=" + quote(page_title)
            )
        metadata: dict[str, object] = {
            "cpdl_page_id": page_id,
            "page_title": page_title,
            "page_url": page_url,
            "voicing": terms,
        }
        work = WorkDescriptor(
            work_id=WorkId(f"cpdl:{page_id or page_title}"),
            title=str(row.get("title") or page_title),
            composer=str(row.get("composer") or None) or None,
            catalogue_number=str(row.get("catalogue_hint") or None) or None,
            metadata=metadata,
        )
        return CandidateRepresentation(
            candidate_id=CandidateId(f"cpdl:{page_id or page_title}"),
            work_descriptor=work,
            provider_id=self.provider_id,
            format=OutputFormat.PDF,
            origin="cpdl",
            public_domain=True,
            quality=QualityLevel.FULL_NOTATION,
            confidence=Confidence(0.5),
            download_url=None,
            view_url=page_url,
            downloadable=False,
            manual_download=True,
            remote_id=str(page_id or page_title),
            metadata=metadata,
        )

    # -- circuitos NO usados por esta integración -------------------------------

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        raise NotImplementedError("CPDL no participa en resolve: la búsqueda es por catálogo")

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        raise NotImplementedError("CPDL no ofrece descarga gestionada: se abre la página wiki")
