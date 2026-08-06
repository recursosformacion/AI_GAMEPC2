"""V3.1 — OSAP Platform API public contract (DTOs).

These are the *public* contract of the REST API. They are independent of the domain
model: they never reuse internal domain Value Objects, so a change to, e.g.,
`WorkDescriptor` cannot break `SearchResponse`. They are immutable (frozen) and typed.
FastAPI only serializes/validates them; they do not depend on the domain.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SearchRequest(_Frozen):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={"examples": [{"query": "Ave Verum KV 618", "limit": 10}]},
    )
    query: str
    limit: int = 10


class WorkInfo(_Frozen):
    work_id: str
    title: str
    composer: str | None = None
    catalogue: str | None = None


class RepresentationInfo(_Frozen):
    provider: str
    format: str
    confidence: float = 0.0


class EvidenceInfo(_Frozen):
    source: str
    code: str
    score: float = 0.0


class SearchResultItem(_Frozen):
    work: WorkInfo
    representation: RepresentationInfo
    score: float
    evidence: list[EvidenceInfo] = []


class SearchResponse(_Frozen):
    search_id: str
    results: list[SearchResultItem] = []


class JobCreateRequest(_Frozen):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={"examples": [{"type": "provider-sync"}]},
    )
    type: str


class JobResponse(_Frozen):
    job_id: str
    type: str
    state: str
    progress: int = 0
    result: dict[str, object] = {}


class ProviderResponse(_Frozen):
    provider_id: str
    name: str
    available: bool
    formats: list[str] = []
    last_sync: str | None = None


class KnowledgeObservationDTO(_Frozen):
    execution_id: str
    source: str
    field: str
    value: str
    provider: str | None = None


class KnowledgeFactDTO(_Frozen):
    fact_type: str
    field: str
    value: str
    count: int


class KnowledgeSuggestionDTO(_Frozen):
    suggestion_type: str
    field: str
    source_value: str
    target_value: str
    reason: str


class KnowledgeResponse(_Frozen):
    observations: list[KnowledgeObservationDTO] = []
    facts: list[KnowledgeFactDTO] = []
    suggestions: list[KnowledgeSuggestionDTO] = []


class SystemHealthResponse(_Frozen):
    status: str


class SystemVersionResponse(_Frozen):
    version: str


class SystemStatisticsResponse(_Frozen):
    providers: int
    searches: int
    jobs: int
    knowledge_observations: int
    knowledge_facts: int
    knowledge_suggestions: int


class ErrorBody(_Frozen):
    code: str
    message: str
    details: dict[str, object] = {}


class SuccessEnvelope(_Frozen, Generic[T]):  # noqa: UP046
    success: bool
    request_id: str
    data: T


class ErrorEnvelope(_Frozen):
    success: bool
    request_id: str
    error: ErrorBody
