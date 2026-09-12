"""CoreMixin: contrato tipado del estado compartido y helpers transversales (F5.4).

`PlatformApiCore` declara el estado y los helpers que los mixins de dominio consumen desde
la instancia compuesta. Cada mixin declara aquí únicamente aquello que usa (regla: el tipado
refleja las dependencias reales, no el `__init__` completo). Las implementaciones reales
(`__init__`/helpers) viven en `PlatformApi` (main.py) hasta que cada dominio se extraiga.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.api.contracts import RepresentationInfo
from src.osap.api.platform._support import _NORMALIZER
from src.osap.domain.normalization import stable_id

if TYPE_CHECKING:
    from threading import Lock

    from src.osap.api.contracts import JobResponse, ProviderResponse, SearchResponse, SearchResultItem
    from src.osap.api.platform._support import KnowledgeStore, SessionSources, SourceCatalog
    from src.osap.application.composers_service import ComposersService
    from src.osap.bootstrap.container import Container
    from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
    from src.osap.infrastructure.state.op.memory import MemoryStore as OpStore
    from src.osap.infrastructure.state.resolution_store import _MemoryStore as ResolutionStore


class PlatformApiCore:
    """Estado compartido usado por los mixins (contrato mínimo por dominio)."""

    _container: Container
    _knowledge: KnowledgeStore
    _searches: dict[str, SearchResponse]
    _search_cache: dict[str, SearchResponse]
    _work_rep_cache: dict[str, list[RepresentationInfo]]
    _work_rep_order: list[str]
    _work_detail_cache: dict[str, dict[str, object]]
    _catalog: SourceCatalog
    _sessions: SessionSources
    _suggestion_counter: int
    _jobs: dict[str, JobResponse]
    _job_counter: int
    _representations: dict[str, dict[str, object]]
    _oidc_pending: dict[str, dict[str, object]]
    _oidc_pending_path: str
    _oidc_pending_lock: Lock
    _store: OpStore
    _resolution_store: ResolutionStore
    _acquisition: AcquisitionService

    # Helpers transversales usados por varios dominios (implementados en PlatformApi).
    def _paginate(
        self, results: list[SearchResultItem], total: int, page: int, limit: int
    ) -> list[SearchResultItem]:
        start = (page - 1) * limit
        return results[start : start + limit]


    def _to_rep(self, m: object, work: object) -> RepresentationInfo:
        """Construye una RepresentationInfo a partir de un candidato (y la registra).

        El id es **determinista** para las representaciones del índice
        (`idx-<work_id>-<provider>-<format>`), de modo que `view`/`download` pueden
        resolverse en el backend aunque se haya reiniciado el proceso (no dependen de
        la caché en memoria).
        """
        fmt = getattr(m, "format", None)
        provider = getattr(m, "provider_id", None)
        confidence = getattr(m, "confidence", None)
        descriptor = getattr(m, "work_descriptor", None)
        download = getattr(m, "download_url", None)
        view = getattr(m, "view_url", None)
        provider_id = provider.value if provider is not None else ""
        # MusicBrainz solo tiene metadata (no fichero): no ofrecer descarga. El enlace
        # (url) apunta a la página web humana para "abrir en MusicBrainz".
        is_metadata_only = provider_id == "musicbrainz"
        # RISM/IMSLP/etc.: sin fichero directo -> available=False y url = página del
        # registro (p. ej. opac.rism.info) para "abrir en el proveedor".
        available = bool(download) and not is_metadata_only
        url = download or view
        fmt_value = fmt.value if fmt is not None else "score"
        candidate_id = getattr(getattr(m, "candidate_id", None), "value", "") or ""
        if candidate_id.startswith("index-"):
            # candidate_id = "index-<work_id>-<provider>"
            work_part = candidate_id.split("-")[1] if len(candidate_id.split("-")) > 1 else ""
            rep_id = f"idx-{work_part}-{provider_id}-{fmt_value}"
        else:
            rep_id = f"r-{stable_id(provider_id, download or view or candidate_id, fmt_value)}"
        self._representations[rep_id] = {
            "download_url": download,
            "view_url": view,
            "composer": getattr(work, "composer", None),
            "title": getattr(work, "title", None),
            "catalogue": getattr(work, "catalogue_number", None),
            "format": fmt.value if fmt is not None else None,
        }
        # Metadatos específicos de la fuente (p. ej. voicing CPDL): viajan con la
        # representación/origen, nunca se copian a `works`.
        raw_metadata = getattr(m, "metadata", None)
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) and raw_metadata else None
        return RepresentationInfo(
            id=rep_id,
            provider=provider_id,
            format=fmt.value if fmt is not None else "musicxml",
            confidence=confidence.value if confidence is not None else 0.0,
            title=str(getattr(descriptor, "title", None) or ""),
            url=url,
            available=available,
            metadata=metadata,
        )


    def _work_key(self, title: str | None, composer: str | None) -> str:
        """Identidad normalizada de la obra (misma clave en cualquier query)."""
        core = _NORMALIZER.comparison_title(title or "", composer)
        comp = _NORMALIZER.canonical_composer(composer) if composer else ""
        return f"{core}|{comp}"



    def list_providers(self) -> list[ProviderResponse]:
        """Implementado por el mixin de providers; usado desde búsqueda (modelo de estudio)."""
        raise NotImplementedError

    def _require_admin(self, token: str | None) -> None:
        """Implementado por el mixin de votos/usuarios; consumido por providers/admin."""
        raise NotImplementedError

    def composers(self) -> ComposersService:
        """Implementado por el mixin de compositores; consumido por correcciones."""
        raise NotImplementedError

    def composer_review_stats(self, token: str | None) -> dict[str, int]:
        """Implementado por el mixin de compositores; consumido por admin (system)."""
        raise NotImplementedError

    def _auth_result(self, code: int, doc: object) -> object:
        """Implementado por el mixin de votos/usuarios; consumido por admin (system)."""
        raise NotImplementedError
