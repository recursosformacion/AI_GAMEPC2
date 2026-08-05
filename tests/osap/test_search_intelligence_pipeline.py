"""Search Intelligence Pipeline — domain integration (V2.1).

Validates that the V2.1 components collaborate as a system, fully isolated from
infrastructure. It uses only fixtures built here. It checks architectural
invariants, NOT provider correctness:

- Canonicalizer produces the canonical form that feeds the query descriptor.
- WorkMatcher decides identity without modifying any WorkDescriptor.
- WorkGrouping groups representations into works correctly.
- Ranking keeps identity (never merges/splits works) and only orders.
- No component breaks the contract of the previous one.
"""

from pathlib import Path

from src.osap.application.canonicalizer import Canonicalizer
from src.osap.application.execution_plan import WorkGroup
from src.osap.application.matcher import DefaultWorkMatcher
from src.osap.application.ranker import DefaultWorkRanker
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.matching import MatchingConfig, MatchLevel
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking import (
    RankingConfig,
    RankingContext,
    RankingCriterion,
    UserPreferences,
)
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

_RULES = Path(__file__).resolve().parents[2] / "resources" / "canonical"


def _descriptor(
    title: str,
    composer: str | None = None,
    catalogue: str | None = None,
    canonical_title: str | None = None,
) -> WorkDescriptor:
    return WorkDescriptor(
        work_id=WorkId("work"),
        title=title,
        composer=composer,
        catalogue_number=catalogue,
        canonical_title=canonical_title,
    )


def _rep(
    pid: str,
    fmt: OutputFormat,
    title: str,
    composer: str | None = None,
    catalogue: str | None = None,
    canonical_title: str | None = None,
    confidence: float = 0.9,
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{pid}-1"),
        work_descriptor=_descriptor(title, composer, catalogue, canonical_title),
        provider_id=ProviderId(pid),
        format=fmt,
        confidence=Confidence(confidence),
    )


def _group(work: WorkDescriptor, reps: list[CandidateRepresentation]) -> WorkGroup:
    return WorkGroup(
        work=work,
        representations=tuple(reps),
        providers=tuple(ProviderId(r.provider_id.value) for r in reps),
    )


def _cluster(candidates: list[CandidateRepresentation], matcher: DefaultWorkMatcher) -> list[WorkGroup]:
    """Group candidates into works using the WorkMatcher identity decisions."""
    groups: list[list[CandidateRepresentation]] = []
    for candidate in candidates:
        placed = False
        for group in groups:
            if matcher.match(group[0].work_descriptor, candidate.work_descriptor).level is MatchLevel.SAME:
                group.append(candidate)
                placed = True
                break
        if not placed:
            groups.append([candidate])
    return [_group(group[0].work_descriptor, group) for group in groups]


def _rank(
    works: tuple[WorkGroup, ...],
    query: WorkDescriptor,
    config: RankingConfig,
    prefs: UserPreferences | None = None,
):
    context = RankingContext(query_descriptor=query, user_preferences=prefs or UserPreferences())
    return DefaultWorkRanker().rank(works, context, config)


def _full_config() -> RankingConfig:
    return RankingConfig(enabled_criteria=tuple(RankingCriterion))


def test_case1_k618_canonicalized_then_grouped_and_ranked() -> None:
    matcher = DefaultWorkMatcher(MatchingConfig())
    canonical = Canonicalizer(_RULES).canonicalize("K618")
    assert canonical.output == "KV 618"

    query = _descriptor(title="Ave Verum", composer="Mozart", catalogue=canonical.output)
    candidate = _rep("imslp", OutputFormat.MUSICXML, "Ave Verum", "Mozart", "KV 618")

    assert matcher.match(query, candidate.work_descriptor).level is MatchLevel.SAME
    groups = _cluster([candidate], matcher)
    assert len(groups) == 1

    result = _rank(tuple(groups), query, _full_config())
    assert len(result.order) == 1
    assert result.order[0].work.work.title == "Ave Verum"
    assert result.order[0].score > 0.9
    assert RankingCriterion.RELEVANCE_CATALOGUE in result.evaluated_criteria


def test_case2_multiple_providers_one_work() -> None:
    matcher = DefaultWorkMatcher(MatchingConfig())
    query = _descriptor(title="Ave Verum", composer="Mozart")
    candidates = [
        _rep("imslp", OutputFormat.PDF, "Ave Verum Corpus", "Mozart", canonical_title="Ave Verum Corpus"),
        _rep("openscore", OutputFormat.MUSICXML, "Ave Verum Corpus", "Mozart", canonical_title="Ave Verum Corpus"),
        _rep("musescore", OutputFormat.MIDI, "Ave Verum Corpus", "Mozart", canonical_title="Ave Verum Corpus"),
    ]

    groups = _cluster(candidates, matcher)
    assert len(groups) == 1
    group = groups[0]
    assert len(group.representations) == 3
    assert {r.provider_id.value for r in group.representations} == {"imslp", "openscore", "musescore"}

    result = _rank((group,), query, _full_config())
    assert len(result.order) == 1
    assert result.order[0].work is group


def test_case3_sonata_multiple_composers_multiple_groups() -> None:
    matcher = DefaultWorkMatcher(MatchingConfig())
    query = _descriptor(title="Sonata")
    candidates = [
        _rep("a", OutputFormat.PDF, "Sonata", "Mozart", confidence=0.9),
        _rep("b", OutputFormat.PDF, "Sonata", "Beethoven", confidence=0.5),
        _rep("c", OutputFormat.PDF, "Sonata", "Schubert", confidence=0.7),
    ]

    groups = _cluster(candidates, matcher)
    assert len(groups) == 3  # composer differs -> three distinct works

    config = RankingConfig(
        enabled_criteria=(RankingCriterion.RELEVANCE_TITLE, RankingCriterion.QUALITY_CONFIDENCE),
        weights={
            RankingCriterion.RELEVANCE_TITLE: 0.25,
            RankingCriterion.QUALITY_CONFIDENCE: 0.20,
        },
    )
    result = _rank(tuple(groups), query, config)
    ordered = [score.work.work.composer for score in result.order]
    assert ordered == ["Mozart", "Schubert", "Beethoven"]
    assert len(result.order) == 3  # ranking keeps identity: no merging


def test_case4_same_work_three_formats_prefers_musicxml() -> None:
    matcher = DefaultWorkMatcher(MatchingConfig())
    query = _descriptor(title="Ave Verum", composer="Mozart", catalogue="KV 618")
    candidates = [
        _rep("imslp", OutputFormat.MUSICXML, "Ave Verum", "Mozart", "KV 618"),
        _rep("openscore", OutputFormat.MEI, "Ave Verum", "Mozart", "KV 618"),
        _rep("omr", OutputFormat.PDF, "Ave Verum", "Mozart", "KV 618"),
    ]

    groups = _cluster(candidates, matcher)
    assert len(groups) == 1
    assert len(groups[0].representations) == 3

    prefs = UserPreferences(desired_format=OutputFormat.MUSICXML)
    config = RankingConfig(
        enabled_criteria=(RankingCriterion.PREFERENCE_FORMAT,),
        weights={RankingCriterion.PREFERENCE_FORMAT: 1.0},
    )
    result = _rank((groups[0],), query, config, prefs)
    assert len(result.order) == 1
    reason = next(r for r in result.order[0].reasons if r.criterion is RankingCriterion.PREFERENCE_FORMAT)
    assert reason.field_score == 1.0


def test_workmatcher_does_not_modify_descriptors() -> None:
    matcher = DefaultWorkMatcher(MatchingConfig())
    query = _descriptor("Ave Verum", "Mozart", "KV 618")
    def _identity(candidate: CandidateRepresentation) -> tuple[str, str | None, str | None]:
        return (
            candidate.work_descriptor.title,
            candidate.work_descriptor.composer,
            candidate.work_descriptor.catalogue_number,
        )

    candidate = _rep("imslp", OutputFormat.MUSICXML, "Ave Verum", "Mozart", "KV 618")
    before = _identity(candidate)
    matcher.match(query, candidate.work_descriptor)
    assert _identity(candidate) == before


def test_ranking_keeps_identity() -> None:
    matcher = DefaultWorkMatcher(MatchingConfig())
    candidates = [
        _rep("a", OutputFormat.PDF, "Sonata", "Mozart", confidence=0.9),
        _rep("b", OutputFormat.PDF, "Sonata", "Beethoven", confidence=0.5),
    ]
    groups = _cluster(candidates, matcher)
    config = RankingConfig(enabled_criteria=(RankingCriterion.QUALITY_CONFIDENCE,))
    result = _rank(tuple(groups), _descriptor("Sonata"), config)
    # Ranking only orders; it does not change how many works exist.
    assert {score.work.work.composer for score in result.order} == {"Mozart", "Beethoven"}
