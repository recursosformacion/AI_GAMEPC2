from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.cost_level import CostLevel
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.cache import InMemoryCache


class _Fake:
    def __init__(self, pid: str, cost: CostLevel, formats: tuple[OutputFormat, ...] = ()) -> None:
        self.pid = ProviderId(pid)
        self._cost = cost
        self._formats = formats
        self.hits = 0

    @property
    def provider_id(self) -> ProviderId:
        return self.pid

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(provider_id=self.pid, cost_level=self._cost, formats=self._formats)

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        self.hits += 1
        work = WorkDescriptor(work_id=WorkId(self.pid.value), title=f"work {self.pid.value}")
        return (
            CandidateRepresentation(
                candidate_id=CandidateId(self.pid.value),
                work_descriptor=work,
                provider_id=self.pid,
                format=OutputFormat.PDF,
                quality=QualityLevel.FULL_NOTATION,
            ),
        )

    def metadata(self) -> object:
        raise NotImplementedError

    def resolve(self, request: SearchRequest) -> CandidateRepresentation | None:
        return None

    def download(self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None) -> object:
        raise NotImplementedError


def _orchestrator() -> tuple[ProviderOrchestrator, _Fake, _Fake]:
    manager = CatalogManager()
    free = _Fake("filesystem", CostLevel.FREE, formats=(OutputFormat.PDF,))
    expensive = _Fake("omr", CostLevel.EXPENSIVE, formats=(OutputFormat.MUSICXML,))
    manager.register(free)
    manager.register(expensive)
    return ProviderOrchestrator(manager, cache=InMemoryCache()), free, expensive


def test_plain_query_queries_all_providers() -> None:
    orchestrator, free, expensive = _orchestrator()
    result = orchestrator.search(SearchRequest(composer="Mozart"))
    # ADR-0020 (revised): all providers are consulted (no early-stop on the first).
    assert [p.value for p in result.providers_used] == ["filesystem", "omr"]
    assert expensive.hits == 1
    assert free.hits == 1


def test_format_request_queries_all_providers() -> None:
    orchestrator, free, expensive = _orchestrator()
    result = orchestrator.search(SearchRequest(composer="Mozart", desired_format=OutputFormat.MUSICXML))
    assert [p.value for p in result.providers_used] == ["filesystem", "omr"]
    assert expensive.hits == 1
    assert free.hits == 1


def test_expensive_provider_is_queried_even_when_free_is_sufficient() -> None:
    orchestrator, _, expensive = _orchestrator()
    orchestrator.search(SearchRequest(title="Ave Verum"))
    orchestrator.search(SearchRequest(title="Ave Verum", desired_format=OutputFormat.PDF))
    assert expensive.hits == 2


def test_search_results_are_cached() -> None:
    orchestrator, free, _ = _orchestrator()
    first = orchestrator.search(SearchRequest(title="Ave Verum"))
    second = orchestrator.search(SearchRequest(title="Ave Verum"))
    assert first.cached is False
    assert second.cached is True
    assert free.hits == 1
