from src.osap.application.evidence_engine import EvidenceEngine
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.evidence import EvidenceReasonKind
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.score_ranking import ScoreRanking
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _candidate(
    pid: str,
    confidence: float = 0.99,
    quality: QualityLevel = QualityLevel.HUMAN_VALIDATED,
    fmt: OutputFormat = OutputFormat.MUSICXML,
    checksum: str | None = "abc",
    completeness: float = 1.0,
) -> CandidateRepresentation:
    work = WorkDescriptor(work_id=WorkId("work"), title="Ave Verum", composer="Mozart")
    return CandidateRepresentation(
        candidate_id=CandidateId(pid),
        work_descriptor=work,
        provider_id=ProviderId(pid),
        format=fmt,
        quality=quality,
        confidence=Confidence(confidence),
        checksum=checksum,
        completeness=completeness,
        public_domain=True,
    )


def test_explain_builds_structured_evidence() -> None:
    chosen = _candidate("omr")
    scores = (ScoreRanking(candidate=chosen, total=0.992, details={"format": 3.0}),)
    evidence = EvidenceEngine().explain(chosen, ResolveRequest(desired_format=OutputFormat.MUSICXML), scores)

    assert evidence.provider_id.value == "omr"
    assert evidence.ranking_score == 0.992
    assert evidence.checksum == "abc"
    assert evidence.metrics.confidence == 0.99
    assert evidence.metrics.quality == 1.0
    assert evidence.metrics.completeness == 1.0

    by_kind = {reason.kind: reason for reason in evidence.reasons}
    assert by_kind[EvidenceReasonKind.CONFIDENCE].satisfied is True
    assert by_kind[EvidenceReasonKind.FORMAT].satisfied is True
    assert by_kind[EvidenceReasonKind.PUBLIC_DOMAIN].satisfied is True
    assert by_kind[EvidenceReasonKind.QUALITY].satisfied is True
    assert by_kind[EvidenceReasonKind.COMPLETENESS].satisfied is True
    assert by_kind[EvidenceReasonKind.CHECKSUM].satisfied is True


def test_unmatched_format_is_recorded_as_not_satisfied() -> None:
    chosen = _candidate("imslp", fmt=OutputFormat.PDF)
    evidence = EvidenceEngine().explain(chosen, ResolveRequest(desired_format=OutputFormat.MUSICXML), ())
    by_kind = {reason.kind: reason for reason in evidence.reasons}
    assert by_kind[EvidenceReasonKind.FORMAT].satisfied is False
    assert by_kind[EvidenceReasonKind.FORMAT].detail == "pdf"


def test_missing_checksum_recorded() -> None:
    chosen = _candidate("filesystem", checksum=None)
    evidence = EvidenceEngine().explain(chosen, ResolveRequest(), ())
    by_kind = {reason.kind: reason for reason in evidence.reasons}
    assert by_kind[EvidenceReasonKind.CHECKSUM].satisfied is False


def test_ranking_score_defaults_to_zero_when_chosen_not_in_scores() -> None:
    chosen = _candidate("omr")
    other = _candidate("imslp")
    scores = (ScoreRanking(candidate=other, total=0.5, details={}),)
    evidence = EvidenceEngine().explain(chosen, ResolveRequest(), scores)
    assert evidence.ranking_score == 0.0
