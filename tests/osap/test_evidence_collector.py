from src.osap.application.evidence_collector import (
    DefaultEvidenceCollector,
    MatchEvidenceContributor,
    RankingEvidenceContributor,
    SelectionEvidenceContributor,
)
from src.osap.application.execution_plan import WorkGroup
from src.osap.application.matcher import DefaultWorkMatcher
from src.osap.application.ranker import DefaultWorkRanker
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.evidence import (
    Evidence,
    EvidenceCode,
    EvidenceField,
    EvidenceItem,
    EvidenceReason,
    EvidenceReasonKind,
    EvidenceResult,
    EvidenceSource,
    EvidenceStrength,
    EvidenceSummary,
)
from src.osap.domain.matching import MatchingConfig, MatchLevel, MatchResult
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking import RankingConfig, RankingContext, RankingCriterion, RankingResult
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId, WorkIdentifier
from src.osap.domain.work_descriptor import WorkDescriptor


def _work(title: str = "Ave Verum", composer: str = "Mozart", catalogue: str | None = "KV 618") -> WorkDescriptor:
    return WorkDescriptor(work_id=WorkId("w"), title=title, composer=composer, catalogue_number=catalogue)


def _rep(catalogue: str | None = "KV 618") -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId("omr-1"),
        work_descriptor=_work(catalogue=catalogue),
        provider_id=ProviderId("omr"),
        format=OutputFormat.MUSICXML,
        confidence=Confidence(0.9),
    )


def _match() -> MatchResult:
    return DefaultWorkMatcher(MatchingConfig()).match(_work(), _work())


def _ranking(catalogue: str | None = "KV 618") -> RankingResult:
    group = WorkGroup(
        work=_work(catalogue=catalogue), representations=(_rep(catalogue),), providers=(ProviderId("omr"),)
    )
    context = RankingContext(query_descriptor=_work(catalogue="KV 618"))
    config = RankingConfig(enabled_criteria=(RankingCriterion.RELEVANCE_CATALOGUE,))
    return DefaultWorkRanker().rank((group,), context, config)


def _selection_evidence() -> Evidence:
    return Evidence(
        provider_id=ProviderId("omr"),
        reasons=(
            EvidenceReason(EvidenceReasonKind.FORMAT, True, "musicxml"),
            EvidenceReason(EvidenceReasonKind.CHECKSUM, False, "abc"),
        ),
    )


def test_evidence_item_and_field_are_typed() -> None:
    item = EvidenceItem(
        source=EvidenceSource.MATCHER,
        code=EvidenceCode.CATALOGUE_MATCH,
        score=1.0,
        fields=(EvidenceField("catalogue", "KV 618"),),
    )
    assert item.source is EvidenceSource.MATCHER
    assert item.code is EvidenceCode.CATALOGUE_MATCH
    assert item.score == 1.0
    assert item.fields[0].name == "catalogue"
    assert item.fields[0].value == "KV 618"


def test_evidence_summary_and_result() -> None:
    summary = EvidenceSummary(matcher_score=1.0, ranking_score=0.5, selection_score=0.25, overall_score=0.7)
    result = EvidenceResult(items=(), summary=summary, overall_score=0.7)
    assert result.summary is summary
    assert result.overall_score == 0.7


def test_matcher_contributor_maps_reasons() -> None:
    items = MatchEvidenceContributor(_match()).to_evidence()
    assert all(item.source is EvidenceSource.MATCHER for item in items)
    codes = {item.code for item in items}
    assert EvidenceCode.CATALOGUE_MATCH in codes
    assert EvidenceCode.COMPOSER_MATCH in codes
    assert EvidenceCode.TITLE_MATCH in codes
    assert all(item.score == 1.0 for item in items)


def test_ranking_contributor_maps_reasons() -> None:
    items = RankingEvidenceContributor(_ranking("KV 618")).to_evidence()
    assert all(item.source is EvidenceSource.RANKER for item in items)
    assert any(item.code is EvidenceCode.RELEVANCE for item in items)


def test_selection_contributor_maps_reasons() -> None:
    items = SelectionEvidenceContributor(_selection_evidence()).to_evidence()
    assert all(item.source is EvidenceSource.SELECTION for item in items)
    assert all(item.code is EvidenceCode.SELECTED_REPRESENTATION for item in items)
    scores = [item.score for item in items]
    assert scores == [1.0, 0.0]  # satisfied -> 1.0, not satisfied -> 0.0


def test_collector_aggregates_scores() -> None:
    match = _match()  # 3 items @ 1.0
    ranking = _ranking("KV 620")  # catalogue mismatch -> 1 item @ 0.0
    selection = _selection_evidence()  # 2 items @ 1.0 and 0.0
    result = DefaultEvidenceCollector().collect(
        (
            MatchEvidenceContributor(match),
            RankingEvidenceContributor(ranking),
            SelectionEvidenceContributor(selection),
        )
    )
    assert result.summary.matcher_score == 1.0
    assert result.summary.ranking_score == 0.0
    assert result.summary.selection_score == 0.5
    assert abs(result.overall_score - (4.0 / 6.0)) < 1e-9
    assert result.summary.overall_score == result.overall_score


def test_overall_score_is_mean_of_all_items() -> None:
    collector = DefaultEvidenceCollector()
    result = collector.collect((MatchEvidenceContributor(_match()),))
    assert result.overall_score == 1.0
    empty = collector.collect(())
    assert empty.overall_score == 0.0
    assert empty.items == ()


def test_determinism() -> None:
    collector = DefaultEvidenceCollector()
    contributors = (
        MatchEvidenceContributor(_match()),
        RankingEvidenceContributor(_ranking("KV 618")),
        SelectionEvidenceContributor(_selection_evidence()),
    )
    assert collector.collect(contributors) == collector.collect(contributors)


def test_inputs_are_not_modified() -> None:
    match = _match()
    ranking = _ranking("KV 618")
    selection = _selection_evidence()
    match_before = match.reasons
    ranking_before = ranking.order
    DefaultEvidenceCollector().collect(
        (MatchEvidenceContributor(match), RankingEvidenceContributor(ranking), SelectionEvidenceContributor(selection))
    )
    assert match.reasons == match_before
    assert ranking.order == ranking_before


def test_evidence_strength_mapping() -> None:
    a = WorkDescriptor(
        work_id=WorkId("a"), title="Ave Verum", composer="Mozart", identifiers=(WorkIdentifier("wikidata", "Q123"),)
    )
    b = WorkDescriptor(
        work_id=WorkId("b"), title="Ave Verum", composer="Mozart", identifiers=(WorkIdentifier("wikidata", "Q123"),)
    )
    items = MatchEvidenceContributor(DefaultWorkMatcher(MatchingConfig()).match(a, b)).to_evidence()
    authority = next(item for item in items if item.code is EvidenceCode.WORK_AUTHORITY_MATCH)
    assert authority.strength is EvidenceStrength.CRITICAL


def test_stable_order_of_items() -> None:
    collector = DefaultEvidenceCollector()
    result = collector.collect(
        (
            MatchEvidenceContributor(_match()),
            RankingEvidenceContributor(_ranking("KV 618")),
            SelectionEvidenceContributor(_selection_evidence()),
        )
    )
    sources = [item.source for item in result.items]
    assert sources == [EvidenceSource.MATCHER] * 3 + [EvidenceSource.RANKER] + [EvidenceSource.SELECTION] * 2


def test_evidence_pipeline_integration() -> None:
    """EvidenceCollector end-to-end over the Search Intelligence pipeline."""
    matcher = DefaultWorkMatcher(MatchingConfig())
    query = WorkDescriptor(work_id=WorkId("q"), title="Ave Verum", composer="Mozart", catalogue_number="KV 618")
    candidate = _rep("KV 618")

    assert matcher.match(query, candidate.work_descriptor).level is MatchLevel.SAME
    match_result = matcher.match(query, candidate.work_descriptor)

    group = WorkGroup(work=query, representations=(candidate,), providers=(ProviderId("omr"),))
    ranking = DefaultWorkRanker().rank(
        (group,),
        RankingContext(query_descriptor=query),
        RankingConfig(enabled_criteria=tuple(RankingCriterion)),
    )
    selection = _selection_evidence()

    result = DefaultEvidenceCollector().collect(
        (
            MatchEvidenceContributor(match_result),
            RankingEvidenceContributor(ranking),
            SelectionEvidenceContributor(selection),
        )
    )
    assert result.items
    assert any(item.source is EvidenceSource.MATCHER for item in result.items)
    assert any(item.source is EvidenceSource.RANKER for item in result.items)
    assert any(item.source is EvidenceSource.SELECTION for item in result.items)
    assert 0.0 < result.overall_score <= 1.0
    assert isinstance(result, EvidenceResult)
