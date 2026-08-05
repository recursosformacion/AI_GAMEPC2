from src.osap.application.execution_plan import WorkGroup
from src.osap.application.ranker import DefaultWorkRanker
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking import (
    RankingConfig,
    RankingContext,
    RankingCriterion,
    RankingResult,
    SortingPolicy,
    UserPreferences,
)
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _work(title: str = "Ave Verum", composer: str | None = "Mozart", catalogue: str | None = None) -> WorkDescriptor:
    return WorkDescriptor(work_id=WorkId("work"), title=title, composer=composer, catalogue_number=catalogue)


def _rep(
    pid: str = "omr",
    fmt: OutputFormat = OutputFormat.MUSICXML,
    confidence: float = 0.9,
    completeness: float = 1.0,
    license: str | None = None,
    local_path: str | None = None,
    title: str = "Ave Verum",
    composer: str | None = "Mozart",
    catalogue: str | None = None,
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{pid}-1"),
        work_descriptor=_work(title, composer, catalogue),
        provider_id=ProviderId(pid),
        format=fmt,
        confidence=Confidence(confidence),
        completeness=completeness,
        license=license,
        local_path=local_path,
    )


def _group(
    reps: tuple[CandidateRepresentation, ...],
    title: str = "Ave Verum",
    composer: str | None = "Mozart",
    catalogue: str | None = None,
) -> WorkGroup:
    return WorkGroup(
        work=_work(title, composer, catalogue),
        representations=reps,
        providers=tuple(ProviderId(rep.provider_id.value) for rep in reps),
    )


def _context(
    title: str = "Query",
    composer: str | None = None,
    catalogue: str | None = None,
    fmt: OutputFormat | None = None,
    license: str | None = None,
    providers: tuple[str, ...] = (),
    prefer_local: bool = False,
) -> RankingContext:
    return RankingContext(
        query_descriptor=WorkDescriptor(
            work_id=WorkId("q"), title=title, composer=composer, catalogue_number=catalogue
        ),
        user_preferences=UserPreferences(
            desired_format=fmt, preferred_license=license, allowed_providers=providers, prefer_local=prefer_local
        ),
    )


def _config(
    enabled: tuple[RankingCriterion, ...],
    weights: dict[RankingCriterion, float] | None = None,
    policy: SortingPolicy = SortingPolicy.STABLE,
) -> RankingConfig:
    return RankingConfig(
        enabled_criteria=enabled,
        weights=weights or {criterion: 1.0 for criterion in enabled},
        sorting_policy=policy,
    )


def _rank(works: tuple[WorkGroup, ...], context: RankingContext, config: RankingConfig) -> RankingResult:
    return DefaultWorkRanker().rank(works, context, config)


def test_relevance_by_catalogue() -> None:
    config = _config((RankingCriterion.RELEVANCE_CATALOGUE,))
    context = _context(catalogue="KV 618")
    a = _group((_rep(catalogue="KV 618"),), catalogue="KV 618")
    b = _group((_rep(catalogue="KV 620"),), catalogue="KV 620")
    result = _rank((a, b), context, config)
    assert [item.work.work.catalogue_number for item in result.order] == ["KV 618", "KV 620"]
    assert result.order[0].score == 1.0
    assert result.order[1].score == 0.0


def test_relevance_by_composer() -> None:
    config = _config((RankingCriterion.RELEVANCE_COMPOSER,))
    context = _context(composer="Mozart")
    a = _group((_rep(composer="Mozart"),), composer="Mozart")
    b = _group((_rep(composer="Beethoven"),), composer="Beethoven")
    result = _rank((a, b), context, config)
    assert result.order[0].score == 1.0
    assert result.order[1].score == 0.0


def test_relevance_by_title_partial_and_exact() -> None:
    config = _config((RankingCriterion.RELEVANCE_TITLE,))
    context = _context(title="Ave Verum")
    exact = _group((_rep(title="Ave Verum"),), title="Ave Verum")
    partial = _group((_rep(title="Ave Verum Corpus"),), title="Ave Verum Corpus")
    different = _group((_rep(title="Symphony"),), title="Symphony")
    result = _rank((partial, exact, different), context, config)
    assert result.order[0].score == 1.0  # exact
    assert result.order[1].score == 0.6  # partial
    assert result.order[2].score == 0.0  # different


def test_preferred_format() -> None:
    config = _config((RankingCriterion.PREFERENCE_FORMAT,))
    context = _context(fmt=OutputFormat.MUSICXML)
    a = _group((_rep(fmt=OutputFormat.MUSICXML),))
    b = _group((_rep(fmt=OutputFormat.PDF),))
    result = _rank((a, b), context, config)
    assert result.order[0].score == 1.0
    assert result.order[1].score == 0.0


def test_preferred_license() -> None:
    config = _config((RankingCriterion.PREFERENCE_LICENSE,))
    context = _context(license="public domain")
    a = _group((_rep(license="public domain"),))
    b = _group((_rep(license="CC BY"),))
    result = _rank((a, b), context, config)
    assert result.order[0].score == 1.0
    assert result.order[1].score == 0.0


def test_quality_confidence() -> None:
    config = _config((RankingCriterion.QUALITY_CONFIDENCE,))
    context = _context()
    a = _group((_rep(confidence=0.9),))
    b = _group((_rep(confidence=0.5),))
    result = _rank((a, b), context, config)
    assert result.order[0].score == 0.9
    assert result.order[1].score == 0.5


def test_coverage() -> None:
    config = _config((RankingCriterion.COVERAGE,))
    context = _context()
    three = _group(
        (_rep(fmt=OutputFormat.MUSICXML), _rep(pid="b", fmt=OutputFormat.PDF), _rep(pid="c", fmt=OutputFormat.MIDI))
    )
    one = _group((_rep(fmt=OutputFormat.PDF),))
    result = _rank((three, one), context, config)
    assert result.order[0].score == 1.0
    assert abs(result.order[1].score - (1.0 / 3.0)) < 1e-9


def test_disabled_criterion_is_not_evaluated() -> None:
    config = _config((RankingCriterion.RELEVANCE_TITLE,))
    context = _context(title="Ave Verum")
    a = _group((_rep(composer="Mozart"),), composer="Mozart")
    b = _group((_rep(composer="Beethoven"),), composer="Beethoven")
    result = _rank((a, b), context, config)
    assert RankingCriterion.RELEVANCE_COMPOSER not in result.evaluated_criteria
    assert result.order[0].score == result.order[1].score


def test_different_weights_change_ordering() -> None:
    context = _context(fmt=OutputFormat.MUSICXML)
    a = _group((_rep(fmt=OutputFormat.MUSICXML, confidence=0.5),))
    b = _group((_rep(fmt=OutputFormat.PDF, confidence=0.9),))
    format_heavy = _config(
        (RankingCriterion.PREFERENCE_FORMAT, RankingCriterion.QUALITY_CONFIDENCE),
        weights={
            RankingCriterion.PREFERENCE_FORMAT: 0.8,
            RankingCriterion.QUALITY_CONFIDENCE: 0.2,
        },
    )
    assert _rank((a, b), context, format_heavy).order[0].work is a
    quality_heavy = _config(
        (RankingCriterion.PREFERENCE_FORMAT, RankingCriterion.QUALITY_CONFIDENCE),
        weights={
            RankingCriterion.PREFERENCE_FORMAT: 0.2,
            RankingCriterion.QUALITY_CONFIDENCE: 0.8,
        },
    )
    assert _rank((a, b), context, quality_heavy).order[0].work is b


def test_score_normalized_by_evaluated_only() -> None:
    config = _config((RankingCriterion.RELEVANCE_COMPOSER, RankingCriterion.RELEVANCE_CATALOGUE))
    context = _context(composer="Mozart", catalogue="KV 618")
    # b lacks a catalogue: the catalogue criterion is skipped and never penalizes.
    a = _group((_rep(composer="Mozart", catalogue="KV 618"),), composer="Mozart", catalogue="KV 618")
    b = _group((_rep(composer="Mozart", catalogue=None),), composer="Mozart", catalogue=None)
    result = _rank((a, b), context, config)
    assert result.order[0].score == 1.0
    assert result.order[1].score == 1.0  # only composer evaluated -> normalized to 1.0


def test_determinism() -> None:
    config = _config((RankingCriterion.RELEVANCE_CATALOGUE,))
    context = _context(catalogue="KV 618")
    works = (
        _group((_rep(catalogue="KV 618"),), catalogue="KV 618"),
        _group((_rep(catalogue="KV 620"),), catalogue="KV 620"),
    )
    first = _rank(works, context, config)
    second = _rank(works, context, config)
    assert first == second


def test_workgroups_not_modified() -> None:
    config = _config((RankingCriterion.RELEVANCE_CATALOGUE,))
    context = _context(catalogue="KV 618")
    group = _group((_rep(catalogue="KV 618"),), catalogue="KV 618")
    before = (group.work.title, group.work.catalogue_number, len(group.representations))
    _rank((group,), context, config)
    assert (group.work.title, group.work.catalogue_number, len(group.representations)) == before


def test_evaluated_criteria() -> None:
    config = _config((RankingCriterion.RELEVANCE_CATALOGUE, RankingCriterion.QUALITY_CONFIDENCE))
    context = _context(catalogue="KV 618")
    group = _group((_rep(catalogue="KV 618"),), catalogue="KV 618")
    result = _rank((group,), context, config)
    assert result.evaluated_criteria == (RankingCriterion.RELEVANCE_CATALOGUE, RankingCriterion.QUALITY_CONFIDENCE)


def test_ranking_reason_correct() -> None:
    config = _config((RankingCriterion.QUALITY_CONFIDENCE,), weights={RankingCriterion.QUALITY_CONFIDENCE: 0.4})
    context = _context()
    group = _group((_rep(confidence=0.95),))
    result = _rank((group,), context, config)
    reason = result.order[0].reasons[0]
    assert reason.criterion is RankingCriterion.QUALITY_CONFIDENCE
    assert reason.field_score == 0.95
    assert reason.weight == 0.4
    assert abs(reason.contribution - 0.38) < 1e-9
    assert abs(result.order[0].score - 0.95) < 1e-9


def test_order_is_descending() -> None:
    config = _config((RankingCriterion.RELEVANCE_CATALOGUE,))
    context = _context(catalogue="KV 618")
    works = tuple(_group((_rep(catalogue=c),), catalogue=c) for c in ("KV 620", "KV 618", "KV 619"))
    result = _rank(works, context, config)
    scores = [item.score for item in result.order]
    assert scores == sorted(scores, reverse=True)
    assert result.order[0].work.work.catalogue_number == "KV 618"


def test_stable_sorting_keeps_input_order_for_ties() -> None:
    config = _config((RankingCriterion.RELEVANCE_CATALOGUE,), policy=SortingPolicy.STABLE)
    context = _context(catalogue="KV 618")
    # Both groups match identically (same catalogue): tie must keep input order.
    a = _group((_rep(pid="a", catalogue="KV 618"),), catalogue="KV 618")
    b = _group((_rep(pid="b", catalogue="KV 618"),), catalogue="KV 618")
    result = _rank((a, b), context, config)
    assert [item.work.representations[0].provider_id.value for item in result.order] == ["a", "b"]
