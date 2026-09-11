"""Búsqueda: requests/responses de la API pública."""

from pydantic import ConfigDict

from .base import _Frozen


class SearchRequest(_Frozen):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {"query": "Ave Verum KV 618", "limit": 10},
                {"query": "Mozart", "composer": "Mozart", "limit": 20},
            ]
        },
    )
    query: str = ""
    limit: int = 10
    page: int = 1
    composer: str | None = None
    title: str | None = None
    catalogue: str | None = None
    instrumentation: str | None = None
    language: str | None = None
    formats: list[str] = []
    providers: list[str] = []
    voices: list[str] = []
    # Macro-familias de género (nombres visibles del catálogo `genres` de osap-storage,
    # p. ej. "Música Clásica / Docta"). El backend los resuelve a genre_id y solo el
    # índice local (obras OMR categorizadas) los aplica; el resto de fuentes los ignora.
    genres: list[str] = []


class WorkInfo(_Frozen):
    work_id: str
    title: str
    composer: str | None = None
    catalogue: str | None = None
    collection: str | None = None


class RepresentationInfo(_Frozen):
    id: str
    provider: str
    format: str
    confidence: float = 0.0
    url: str | None = None  # link a la fuente original (para abrir cuando no hay fichero servible)
    title: str | None = None
    available: bool = True  # hay fichero descargable vía el endpoint de descarga
    # Metadatos específicos de la fuente (p. ej. voicing CPDL). Nunca se copian a `works`.
    metadata: dict[str, object] | None = None


class EvidenceInfo(_Frozen):
    source: str
    code: str
    score: float = 0.0


class WorkRelationships(_Frozen):
    aliases: list[str] = []
    related_catalogues: list[str] = []
    editions: list[str] = []
    parent_work: str | None = None
    movements: list[str] = []


class SearchResultItem(_Frozen):
    work: WorkInfo
    representation: RepresentationInfo
    representations: list[RepresentationInfo] = []
    score: float
    evidence: list[EvidenceInfo] = []
    relationships: WorkRelationships | None = None


class SearchResponse(_Frozen):
    search_id: str
    results: list[SearchResultItem] = []
    total: int = 0
    page: int = 1
    per_page: int = 10
    status: str = "done"  # running | done | error
    progress: int = 100  # 0..100
    providers: list[str] = []  # "provider: N candidato(s)" conforme se consultan


