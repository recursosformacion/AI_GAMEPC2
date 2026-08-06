"""V3.1 — OSAP Platform API application layer.

Use cases exposed by the API. It calls existing Application Services (never domain
internals directly) and produces the public contract DTOs. Pure orchestration; no HTTP.
"""

import uuid
from datetime import UTC, datetime

from src.osap.api.contracts import (
    JobResponse,
    KnowledgeFactDTO,
    KnowledgeObservationDTO,
    KnowledgeResponse,
    KnowledgeSuggestionDTO,
    ProviderResponse,
    RepresentationInfo,
    SearchResponse,
    SearchResultItem,
    SystemStatisticsResponse,
    SystemVersionResponse,
    WorkInfo,
)
from src.osap.application.jobs import DefaultJob
from src.osap.bootstrap.container import Container
from src.osap.domain.jobs import JobContext, JobTrigger
from src.osap.domain.knowledge import KnowledgeBase
from src.osap.domain.resolve_request import ResolveRequestBuilder

VERSION = "1.0.0"


class KnowledgeStore:
    """In-memory read source for the Knowledge API (observations/facts/suggestions)."""

    def __init__(self, base: KnowledgeBase | None = None) -> None:
        self._base = base or KnowledgeBase()

    def base(self) -> KnowledgeBase:
        return self._base

    def set_base(self, base: KnowledgeBase) -> None:
        self._base = base


class PlatformApi:
    """Use cases of the OSAP Platform API, backed by existing application services."""

    def __init__(self, container: Container, knowledge: KnowledgeStore | None = None) -> None:
        self._container = container
        self._knowledge = knowledge or KnowledgeStore()
        self._searches: dict[str, SearchResponse] = {}
        self._jobs: dict[str, JobResponse] = {}
        self._job_counter = 0

    # --- search -------------------------------------------------------------

    def create_search(self, query: str, limit: int) -> tuple[str, SearchResponse]:
        search_id = uuid.uuid4().hex
        response = SearchResponse(search_id=search_id, results=self._run_search(query, limit))
        self._searches[search_id] = response
        return search_id, response

    def get_search(self, search_id: str) -> SearchResponse | None:
        return self._searches.get(search_id)

    def _run_search(self, query: str, limit: int) -> list[SearchResultItem]:
        request = ResolveRequestBuilder().text(query).build()
        engine = self._container.work_resolution_engine()
        ranked = engine.rank(request)
        groups = self._container.work_merge_service().group(ranked)
        results: list[SearchResultItem] = []
        for group in groups[:limit]:
            work = group.work
            rep = group.primary
            if rep is None:
                continue
            results.append(
                SearchResultItem(
                    work=WorkInfo(
                        work_id=work.work_id.value,
                        title=work.title,
                        composer=work.composer,
                        catalogue=work.catalogue_number,
                    ),
                    representation=RepresentationInfo(
                        provider=rep.provider_id.value,
                        format=rep.format.value,
                        confidence=rep.confidence.value,
                    ),
                    score=rep.confidence.value,
                    evidence=[],
                )
            )
        return results

    # --- jobs ---------------------------------------------------------------

    def create_job(self, job_type: str) -> JobResponse:
        self._job_counter += 1
        job_id = f"job-{self._job_counter}"
        context = JobContext(
            execution_id=job_id,
            started_at=datetime.now(UTC),
            triggered_by=JobTrigger.API,
            dry_run=False,
        )
        result = DefaultJob().run(context)
        response = JobResponse(job_id=job_id, type=job_type, state=result.status.value, progress=100, result={})
        self._jobs[job_id] = response
        return response

    def list_jobs(self) -> list[JobResponse]:
        return sorted(self._jobs.values(), key=lambda job: job.job_id)

    def get_job(self, job_id: str) -> JobResponse | None:
        return self._jobs.get(job_id)

    # --- providers ----------------------------------------------------------

    def list_providers(self) -> list[ProviderResponse]:
        return [self._provider_response(provider) for provider in self._container.catalog_manager().providers()]

    def get_provider(self, provider_id: str) -> ProviderResponse | None:
        for provider in self._container.catalog_manager().providers():
            if provider.provider_id.value == provider_id:
                return self._provider_response(provider)
        return None

    @staticmethod
    def _provider_response(provider: object) -> ProviderResponse:
        capabilities = provider.capabilities()  # type: ignore[attr-defined]
        availability = str(capabilities.metadata.get("availability") or "")
        available = availability != "index_missing"
        info = provider.metadata()  # type: ignore[attr-defined]
        return ProviderResponse(
            provider_id=provider.provider_id.value,  # type: ignore[attr-defined]
            name=info.name,
            available=available,
            formats=[f.value for f in capabilities.formats],
            last_sync=None,
        )

    # --- knowledge (read-only) ----------------------------------------------

    def knowledge(self) -> KnowledgeResponse:
        base = self._knowledge.base()
        return KnowledgeResponse(
            observations=[
                KnowledgeObservationDTO(
                    execution_id=o.execution_id,
                    source=o.source.value,
                    field=o.field,
                    value=o.value,
                    provider=o.provider,
                )
                for o in base.observations
            ],
            facts=[
                KnowledgeFactDTO(fact_type=f.fact_type.value, field=f.field, value=f.value, count=f.count)
                for f in base.facts
            ],
            suggestions=[
                KnowledgeSuggestionDTO(
                    suggestion_type=s.suggestion_type.value,
                    field=s.field,
                    source_value=s.source_value,
                    target_value=s.target_value,
                    reason=s.reason,
                )
                for s in base.suggestions
            ],
        )

    # --- system -------------------------------------------------------------

    def health(self) -> str:
        return "ok"

    def version(self) -> SystemVersionResponse:
        return SystemVersionResponse(version=VERSION)

    def statistics(self) -> SystemStatisticsResponse:
        base = self._knowledge.base()
        return SystemStatisticsResponse(
            providers=len(self._container.catalog_manager().providers()),
            searches=len(self._searches),
            jobs=len(self._jobs),
            knowledge_observations=len(base.observations),
            knowledge_facts=len(base.facts),
            knowledge_suggestions=len(base.suggestions),
        )
