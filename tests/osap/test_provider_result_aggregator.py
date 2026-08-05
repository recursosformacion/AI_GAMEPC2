from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.application.provider_result_aggregator import ProviderResultAggregator
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _candidate(
    pid: str,
    cid: str,
    title: str = "Ave Verum",
    composer: str = "Mozart",
    remote_id: str | None = None,
    checksum: str | None = None,
) -> CandidateRepresentation:
    work = WorkDescriptor(work_id=WorkId("work"), title=title, composer=composer)
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=work,
        provider_id=ProviderId(pid),
        format=OutputFormat.PDF,
        quality=QualityLevel.FULL_NOTATION,
        remote_id=remote_id,
        checksum=checksum,
    )


def test_aggregates_candidates_providers_and_diagnostics() -> None:
    agg = ProviderResultAggregator()
    agg.add_candidates(ProviderId("imslp"), (_candidate("imslp", "c1"),))
    agg.add_candidates(ProviderId("omr"), (_candidate("omr", "c2", title="Ave verum corpus"),))
    agg.add_diagnostic("pdmx: unavailable")
    result = agg.result()
    assert [c.candidate_id.value for c in result.candidates] == ["c1", "c2"]
    assert [p.value for p in result.providers_used] == ["imslp", "omr"]
    assert result.diagnostics == ("pdmx: unavailable",)
    assert result.cached is False


def test_deduplicates_same_provider_and_remote_id() -> None:
    agg = ProviderResultAggregator()
    agg.add_candidates(
        ProviderId("imslp"), (_candidate("imslp", "c1", remote_id="r1"), _candidate("imslp", "c2", remote_id="r1"))
    )
    result = agg.result()
    assert len(result.candidates) == 1
    assert result.candidates[0].candidate_id.value == "c1"


def test_deduplicates_same_provider_and_checksum() -> None:
    agg = ProviderResultAggregator()
    agg.add_candidates(
        ProviderId("omr"), (_candidate("omr", "c1", checksum="abc"), _candidate("omr", "c2", checksum="abc"))
    )
    result = agg.result()
    assert len(result.candidates) == 1


def test_keeps_distinct_providers_even_with_same_remote_id() -> None:
    agg = ProviderResultAggregator()
    agg.add_candidates(ProviderId("imslp"), (_candidate("imslp", "c1", remote_id="r1"),))
    agg.add_candidates(ProviderId("omr"), (_candidate("omr", "c2", remote_id="r1"),))
    result = agg.result()
    assert len(result.candidates) == 2


def test_groups_representations_by_work() -> None:
    agg = ProviderResultAggregator()
    agg.add_candidates(
        ProviderId("imslp"), (_candidate("imslp", "c1", title="Ave Verum", composer="Mozart"),)
    )
    agg.add_candidates(
        ProviderId("omr"), (_candidate("omr", "c2", title="Ave verum", composer="Mozart"),)
    )
    result = agg.result()
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.work.title == "Ave Verum"
    assert [c.candidate_id.value for c in group.representations] == ["c1", "c2"]
    assert [p.value for p in group.providers] == ["imslp", "omr"]


def test_does_not_mutate_candidates() -> None:
    agg = ProviderResultAggregator()
    original = _candidate("imslp", "c1")
    agg.add_candidates(ProviderId("imslp"), (original,))
    result = agg.result()
    assert result.candidates[0] is original


def test_empty_result() -> None:
    result = ProviderResultAggregator().result()
    assert result.candidates == ()
    assert result.groups == ()
    assert result.providers_used == ()
    assert result.diagnostics == ()


class _ProvFake:
    """A provider that always returns a single fixed work in a given format."""

    def __init__(self, pid: str, fmt: OutputFormat) -> None:
        self.pid = ProviderId(pid)
        self._fmt = fmt
        self.hits = 0

    @property
    def provider_id(self) -> ProviderId:
        return self.pid

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(provider_id=self.pid, formats=(self._fmt,))

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        self.hits += 1
        work = WorkDescriptor(work_id=WorkId("work"), title="Ave Verum", composer="Mozart")
        return (
            CandidateRepresentation(
                candidate_id=CandidateId(f"{self.pid.value}-1"),
                work_descriptor=work,
                provider_id=self.pid,
                format=self._fmt,
                quality=QualityLevel.FULL_NOTATION,
            ),
        )

    def resolve(self, request: SearchRequest) -> CandidateRepresentation | None:
        return None

    def download(self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None) -> object:
        raise NotImplementedError


def test_two_providers_describing_the_same_work_produce_one_group() -> None:
    manager = CatalogManager()
    imslp = _ProvFake("imslp", OutputFormat.PDF)
    omr = _ProvFake("omr", OutputFormat.MUSICXML)
    manager.register(imslp)
    manager.register(omr)
    orchestrator = ProviderOrchestrator(manager)
    query = SearchRequest(title="Ave Verum", composer="Mozart", desired_format=OutputFormat.MUSICXML)
    result = orchestrator.search(query)

    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.work.title == "Ave Verum"
    assert group.work.composer == "Mozart"
    assert {c.format for c in group.representations} == {OutputFormat.PDF, OutputFormat.MUSICXML}
    assert {p.value for p in group.providers} == {"imslp", "omr"}
    # Not 2 loose candidates: one Work with two representations.
    assert {c.candidate_id.value for c in result.candidates} == {"imslp-1", "omr-1"}
    assert imslp.hits == 1
    assert omr.hits == 1
