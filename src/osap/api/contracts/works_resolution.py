"""Works/sesiones de resolución y envolturas de respuesta."""

from typing import Generic, TypeVar

from pydantic import Field

from .base import _Frozen
from .composers import (
    ComposerResolveCandidateResponse,
    ComposerResolveComposer,
    ComposerResolveEvidenceResponse,
    ComposerResolveSource,
    ComposerResolveWork,
    ResolvedComposerResponse,
)
from .sources_corrections import ErrorBody

T = TypeVar("T")


class WorksNormalized(_Frozen):
    """Transformación determinista del texto recibido (no es resolución)."""

    title_raw: str
    title: str
    composer_raw: str | None = None
    composer: str | None = None
    catalog: str | None = None


class WorksResolvedWork(_Frozen):
    title: str | None = None
    catalog: str | None = None


class WorksResolved(_Frozen):
    """Conclusión obtenida mediante fuentes/evidencias. `composer` puede ser null."""

    work: WorksResolvedWork | None = None
    composer: ResolvedComposerResponse | None = None


class WorksResolveItemRequest(_Frozen):
    id: str | None = None
    composer: ComposerResolveComposer | None = None
    work: ComposerResolveWork
    source: ComposerResolveSource | None = None


class WorksResolveRequest(_Frozen):
    works: list[WorksResolveItemRequest]
    concurrency: int = 4


class WorksResolveItemResponse(_Frozen):
    id: str | None = None
    status: str
    normalized: WorksNormalized
    resolved: WorksResolved
    confidence: float = 0.0
    input_quality: str = "normal"
    candidates: list[ComposerResolveCandidateResponse] = []
    evidence: list[ComposerResolveEvidenceResponse] = []


class WorksResolveSummary(_Frozen):
    total: int
    resolved: int
    ambiguous: int
    not_found: int


class WorksResolveResponse(_Frozen):
    results: list[WorksResolveItemResponse]
    summary: WorksResolveSummary


# --- resolución asíncrona por sesión (ADR-0033 / resolution-store-v1) ---------


class ResolutionPolicy(_Frozen):
    """Política configurable de la sesión. `max_duration_s` es límite de ejecución de la
    adquisición; `ttl_s` es el TTL de conservación de la sesión (independientes)."""

    max_results_to_acquire: int = 500
    max_pages_per_provider: int = 20
    max_duration_s: int = 120
    ttl_s: int = 1800


class ResolutionSessionCreateRequest(_Frozen):
    query: str | None = None
    works: list[WorksResolveItemRequest] | None = None
    providers: list[str] | None = None
    policy: ResolutionPolicy | None = None
    resume_session_id: str | None = None


class ResolutionSessionCreated(_Frozen):
    session_id: str
    status: str
    created_at: str
    expires_at: str


class ResolutionProgress(_Frozen):
    acquired_pages: int = 0
    acquired_works: int = 0
    items_total: int = 0
    items_resolved: int = 0
    items_ambiguous: int = 0
    items_not_found: int = 0


class ResolutionSessionResponse(_Frozen):
    session_id: str
    status: str
    query: str | None = None
    providers: list[str] = Field(default_factory=list)
    policy: ResolutionPolicy = Field(default_factory=ResolutionPolicy)
    progress: ResolutionProgress = Field(default_factory=ResolutionProgress)
    created_at: str
    updated_at: str
    expires_at: str
    error: str | None = None
    selection: dict[str, object] | None = None


class ResolutionItemResponse(_Frozen):
    id: str
    status: str
    resolution_stage: str
    revision: int
    normalized: WorksNormalized | None = None
    resolved: WorksResolved | None = None
    confidence: float = 0.0
    input_quality: str = "normal"
    candidates: list[ComposerResolveCandidateResponse] = []
    evidence: list[ComposerResolveEvidenceResponse] = []


class ResolutionResultsResponse(_Frozen):
    session_id: str
    status: str
    resolution_stage: str
    revision: int = 0
    page: int = 1
    per_page: int = 25
    total: int = 0
    results: list[ResolutionItemResponse] = []


class SuccessEnvelope(_Frozen, Generic[T]):  # noqa: UP046
    success: bool
    request_id: str
    data: T


class ErrorEnvelope(_Frozen):
    success: bool
    request_id: str
    error: ErrorBody
