"""Jobs, providers, knowledge y system (V3.1)."""

from pydantic import ConfigDict

from .base import _Frozen


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
    description: dict[str, str] = {}
    website: str | None = None


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
    storage_target: str | None = None
    read_only: bool = False
    dev_auth_bypass: bool = False


class SystemVersionResponse(_Frozen):
    version: str


class SystemStatisticsResponse(_Frozen):
    providers: int
    searches: int
    jobs: int
    knowledge_observations: int
    knowledge_facts: int
    knowledge_suggestions: int


