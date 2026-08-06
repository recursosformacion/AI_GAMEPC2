from src.osap.application.execution_plan import WorkGroup
from src.osap.application.merge_evidence_contributor import MergeEvidenceContributor
from src.osap.application.merge_service import DefaultMergeService
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.evidence import EvidenceCode, EvidenceSource
from src.osap.domain.merge import MergeConflictType, MergeCriterion, MergePolicy
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId, WorkIdentifier
from src.osap.domain.work_descriptor import WorkDescriptor


def _work(
    title: str = "Ave Verum",
    composer: str | None = "Mozart",
    catalogue: str | None = "KV 618",
    opus: str | None = None,
    subtitle: str | None = None,
    language: str | None = None,
    key: str | None = None,
    creation_year: int | None = None,
    genres: tuple[str, ...] = (),
    instrumentation: tuple[str, ...] = (),
    voices: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    identifiers: tuple[WorkIdentifier, ...] = (),
) -> WorkDescriptor:
    return WorkDescriptor(
        work_id=WorkId("w"),
        title=title,
        composer=composer,
        catalogue_number=catalogue,
        opus=opus,
        subtitle=subtitle,
        language=language,
        key=key,
        creation_year=creation_year,
        genres=genres,
        instrumentation=instrumentation,
        voices=voices,
        aliases=aliases,
        identifiers=identifiers,
    )


def _rep(
    pid: str,
    confidence: float = 0.9,
    **kwargs,
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{pid}-1"),
        work_descriptor=_work(**kwargs),
        provider_id=ProviderId(pid),
        format=OutputFormat.MUSICXML,
        confidence=Confidence(confidence),
    )


def _group(work: WorkDescriptor, reps: tuple[CandidateRepresentation, ...]) -> WorkGroup:
    return WorkGroup(work=work, representations=reps, providers=tuple(ProviderId(r.provider_id.value) for r in reps))


def _merge(work: WorkDescriptor, reps: tuple[CandidateRepresentation, ...], policy: MergePolicy | None = None):
    return DefaultMergeService().merge(_group(work, reps), policy or MergePolicy())


def test_enriches_descriptive_fields() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    reps = (
        _rep("imslp", subtitle="for SATB", language="la", key="D", creation_year=1791),
        _rep("omr", genres=("motet",), instrumentation=("soprano", "alto", "tenor", "bass")),
    )
    result = _merge(group_work, reps)
    md = result.merged_descriptor
    assert md.subtitle == "for SATB"
    assert md.language == "la"
    assert md.key == "D"
    assert md.creation_year == 1791
    assert md.genres == ("motet",)
    assert md.instrumentation == ("alto", "bass", "soprano", "tenor")


def test_identity_never_modified() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    reps = (_rep("imslp", title="Ave Verum Corpus", composer="Mozart", catalogue="KV 618"),)
    result = _merge(group_work, reps)
    md = result.merged_descriptor
    # identity comes from the group, never from a rep
    assert md.title == "Ave Verum"
    assert md.composer == "Mozart"
    assert md.catalogue_number == "KV 618"


def test_identity_conflict_detected() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    reps = (_rep("imslp", title="Ave Verum Corpus", composer="Mozart", catalogue="KV 620"),)
    result = _merge(group_work, reps)
    types = {c.conflict_type for c in result.conflicts}
    assert MergeConflictType.IDENTITY_CONFLICT in types
    catalogue_conflict = next(c for c in result.conflicts if c.field == "catalogue_number")
    assert catalogue_conflict.sources == ("imslp",)


def test_value_conflict_detected_and_resolved() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    reps = (
        _rep("imslp", key="D", confidence=0.9),
        _rep("omr", key="C", confidence=0.5),
    )
    policy = MergePolicy(enabled_criteria=(MergeCriterion.REPRESENTATION_CONFIDENCE,))
    result = _merge(group_work, reps, policy)
    assert any(c.field == "key" and c.conflict_type is MergeConflictType.VALUE_CONFLICT for c in result.conflicts)
    # policy picks the value from the highest-confidence rep (imslp: D)
    assert result.merged_descriptor.key == "D"


def test_authority_conflict_detected() -> None:
    group_work = _work(
        title="Ave Verum", composer="Mozart", catalogue="KV 618", identifiers=(WorkIdentifier("wikidata", "Q1"),)
    )
    reps = (_rep("imslp", identifiers=(WorkIdentifier("wikidata", "Q2"),)),)
    result = _merge(group_work, reps)
    assert any(c.conflict_type is MergeConflictType.AUTHORITY_CONFLICT for c in result.conflicts)


def test_provenance_is_correct() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    reps = (_rep("omr", language="la"),)
    result = _merge(group_work, reps)
    prov = next(p for p in result.provenance if p.field == "language")
    assert prov.value == "la"
    assert prov.source == "omr"
    assert prov.strategy is MergeCriterion.REPRESENTATION_CONFIDENCE
    assert prov.confidence == 0.9


def test_order_independence() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    a = _rep("imslp", key="D", confidence=0.9)
    b = _rep("omr", key="C", confidence=0.5)
    policy = MergePolicy(enabled_criteria=(MergeCriterion.REPRESENTATION_CONFIDENCE,))
    r1 = _merge(group_work, (a, b), policy)
    r2 = _merge(group_work, (b, a), policy)
    assert r1.merged_descriptor == r2.merged_descriptor
    assert set(r1.conflicts) == set(r2.conflicts)


def test_determinism() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    reps = (_rep("imslp", language="la"), _rep("omr", language="la"))
    first = _merge(group_work, reps)
    second = _merge(group_work, reps)
    assert first == second


def test_inputs_are_not_modified() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618", subtitle="x")
    rep = _rep("imslp", subtitle="for SATB")
    before = (group_work.subtitle, rep.work_descriptor.subtitle, len(group_work.genres))
    _merge(group_work, (rep,))
    assert (group_work.subtitle, rep.work_descriptor.subtitle, len(group_work.genres)) == before


def test_evidence_contribution() -> None:
    group_work = _work(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    reps = (_rep("omr", language="la"),)
    result = _merge(group_work, reps)
    items = MergeEvidenceContributor(result).to_evidence()
    assert all(item.source is EvidenceSource.MERGE for item in items)
    assert any(item.code is EvidenceCode.MERGE_FIELD for item in items)
    assert result.evidence
    assert result.evidence == items
