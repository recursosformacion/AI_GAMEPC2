import pytest

from src.osap.application.work_resolver import WorkResolver
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


class TestWorkResolver:
    def test_resolve_builds_descriptor(self) -> None:
        resolver = WorkResolver()
        work = resolver.resolve(ResolveRequest(title="Canço de Comiat", composer="Eduard Toldrà"))
        assert work.title == "Canço de Comiat"
        assert work.composer == "Eduard Toldrà"

    def test_resolve_from_query(self) -> None:
        work = WorkResolver().resolve(ResolveRequest(query="Ave Maria"))
        assert work.title == "Ave Maria"

    def test_resolve_requires_identity(self) -> None:
        with pytest.raises(ScoreResolutionError):
            WorkResolver().resolve(ResolveRequest())

    def test_is_same_work(self) -> None:
        resolver = WorkResolver()
        a = WorkDescriptor(work_id=WorkId("w1"), title="Ave Maria", composer="Franz Schubert")
        same = WorkDescriptor(work_id=WorkId("w2"), title="Ave Maria", composer="Franz Schubert")
        assert resolver.is_same_work(a, same) is True
        other_composer = WorkDescriptor(work_id=WorkId("w3"), title="Ave Maria", composer="Other")
        assert resolver.is_same_work(a, other_composer) is False
        other_title = WorkDescriptor(work_id=WorkId("w4"), title="Different", composer="Franz Schubert")
        assert resolver.is_same_work(a, other_title) is False

    def test_merge_work_collects_aliases(self) -> None:
        base = WorkDescriptor(work_id=WorkId("w1"), title="Ave Maria")
        candidates = (
            CandidateRepresentation(
                candidate_id=CandidateId("c1"),
                work_descriptor=base,
                provider_id=ProviderId("a"),
                format=OutputFormat.PDF,
                metadata={"full_title": "Ave Maria (Schubert)"},
            ),
        )
        merged = WorkResolver().merge_work(candidates)
        assert "Ave Maria (Schubert)" in merged.aliases

    def test_merge_empty_raises(self) -> None:
        with pytest.raises(ScoreResolutionError):
            WorkResolver().merge_work(())
