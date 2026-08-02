from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.rankings import DefaultRankingEngine


def _candidate(
    cid: str, fmt: OutputFormat, confidence: float = 0.5, local: str | None = None
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=WorkDescriptor(work_id=WorkId(cid), title="Ave Maria", composer="Franz Schubert"),
        provider_id=ProviderId("imslp"),
        format=fmt,
        confidence=Confidence(confidence),
        local_path=local,
    )


class TestDefaultRankingEngine:
    def test_desired_format_ranks_highest(self) -> None:
        engine = DefaultRankingEngine()
        musicxml = _candidate("m", OutputFormat.MUSICXML)
        pdf = _candidate("p", OutputFormat.PDF)
        request = ResolveRequest(title="Ave Maria", desired_format=OutputFormat.MUSICXML)
        ranked = engine.rank((pdf, musicxml), request, RankingConfig())
        assert ranked[0] == musicxml

    def test_local_availability_ranks_above_remote(self) -> None:
        engine = DefaultRankingEngine()
        local = _candidate("loc", OutputFormat.MUSICXML, local="/tmp/x.mxl")
        remote = _candidate("rem", OutputFormat.MUSICXML)
        ranked = engine.rank((remote, local), ResolveRequest(title="Ave Maria"), RankingConfig())
        assert ranked[0] == local

    def test_composer_match_boost(self) -> None:
        engine = DefaultRankingEngine()
        exact = CandidateRepresentation(
            candidate_id=CandidateId("x"),
            work_descriptor=WorkDescriptor(work_id=WorkId("x"), title="Ave Maria", composer="Franz Schubert"),
            provider_id=ProviderId("cpdl"),
            format=OutputFormat.MUSICXML,
        )
        vague = CandidateRepresentation(
            candidate_id=CandidateId("v"),
            work_descriptor=WorkDescriptor(work_id=WorkId("v"), title="Ave Maria", composer="F. Schubert"),
            provider_id=ProviderId("cpdl"),
            format=OutputFormat.MUSICXML,
        )
        request = ResolveRequest(title="Ave Maria", composer="Franz Schubert")
        ranked = engine.rank((vague, exact), request, RankingConfig())
        assert ranked[0] == exact

    def test_empty(self) -> None:
        assert DefaultRankingEngine().rank((), ResolveRequest(title="X"), RankingConfig()) == ()
