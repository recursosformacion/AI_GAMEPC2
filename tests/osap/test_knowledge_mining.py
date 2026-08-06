"""Knowledge Mining — domain + application tests (V2.2.d)."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.osap.application.canonicalizer import Canonicalizer
from src.osap.application.execution_plan import WorkGroup
from src.osap.application.knowledge_collector import DefaultKnowledgeCollector
from src.osap.application.knowledge_miner import DefaultKnowledgeMiner
from src.osap.application.matcher import DefaultWorkMatcher
from src.osap.application.merge_service import DefaultMergeService
from src.osap.application.ranker import DefaultWorkRanker
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.knowledge import (
    KnowledgeBase,
    KnowledgeFact,
    KnowledgeFactType,
    KnowledgeObservation,
    KnowledgeSource,
    KnowledgeSuggestion,
    KnowledgeSuggestionType,
)
from src.osap.domain.matching import MatchingConfig, MatchLevel
from src.osap.domain.merge import MergePolicy
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking import RankingConfig, RankingContext, UserPreferences
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.knowledge_collector import IKnowledgeCollector
from src.osap.ports.knowledge_miner import IKnowledgeMiner

_RULES = Path(__file__).resolve().parents[2] / "resources" / "canonical"


def _obs(
    value: str,
    field: str = "catalogue",
    source: KnowledgeSource = KnowledgeSource.MERGE,
    execution_id: str = "exec-1",
    provider: str | None = "imslp",
) -> KnowledgeObservation:
    return KnowledgeObservation(
        execution_id=execution_id, source=source, field=field, value=value, provider=provider
    )


def _base(observations: tuple[KnowledgeObservation, ...]) -> KnowledgeBase:
    return DefaultKnowledgeCollector().collect(observations)


def _mined(observations: tuple[KnowledgeObservation, ...]) -> KnowledgeBase:
    return DefaultKnowledgeMiner().mine(_base(observations))


# --- immutability -----------------------------------------------------------


def test_knowledge_observation_is_immutable() -> None:
    obs = _obs("K.618")
    with pytest.raises(FrozenInstanceError):
        obs.value = "other"  # type: ignore[misc]


def test_knowledge_fact_is_immutable() -> None:
    fact = KnowledgeFact(fact_type=KnowledgeFactType.FREQUENCY, field="catalogue", value="KV 618", count=1)
    with pytest.raises(FrozenInstanceError):
        fact.count = 2  # type: ignore[misc]


def test_knowledge_suggestion_is_immutable() -> None:
    suggestion = KnowledgeSuggestion(
        suggestion_type=KnowledgeSuggestionType.ADD_ALIAS,
        field="catalogue",
        source_value="K618",
        target_value="KV 618",
        reason="x",
    )
    with pytest.raises(FrozenInstanceError):
        suggestion.field = "title"  # type: ignore[misc]


def test_knowledge_base_is_immutable() -> None:
    base = _base((_obs("K.618"),))
    with pytest.raises(FrozenInstanceError):
        base.facts = ()  # type: ignore[misc]


# --- collector --------------------------------------------------------------


def test_collector_is_an_i_knowledge_collector() -> None:
    assert isinstance(DefaultKnowledgeCollector(), IKnowledgeCollector)


def test_collector_builds_knowledge_base_with_observations_only() -> None:
    base = _base((_obs("K.618"), _obs("KV 618", execution_id="exec-2")))
    assert len(base.observations) == 2
    assert base.facts == ()
    assert base.suggestions == ()


def test_collector_normalizes_deduplicates_and_sorts() -> None:
    observations = (
        _obs("B", execution_id="exec-2"),
        _obs("A", execution_id="exec-1"),
        _obs("B", execution_id="exec-2"),
    )
    base = _base(observations)
    assert [o.value for o in base.observations] == ["A", "B"]


# --- miner ------------------------------------------------------------------


def test_miner_is_an_i_knowledge_miner() -> None:
    assert isinstance(DefaultKnowledgeMiner(), IKnowledgeMiner)


def test_miner_produces_facts_and_suggestions() -> None:
    base = _mined((_obs("K.618"), _obs("K.618", execution_id="exec-2")))
    assert len(base.facts) == 1
    assert base.facts[0].fact_type is KnowledgeFactType.FREQUENCY
    assert base.facts[0].count == 2
    assert len(base.suggestions) == 1
    assert base.suggestions[0].suggestion_type is KnowledgeSuggestionType.ADD_ALIAS


def test_fact_generation_traceable() -> None:
    base = _mined((_obs("K.618", execution_id="a"), _obs("K.618", execution_id="b")))
    fact = base.facts[0]
    assert set(fact.observation_ids) == {"a", "b"}
    assert KnowledgeSource.MERGE in fact.sources


def test_suggestion_references_facts() -> None:
    base = _mined((_obs("K.618"), _obs("K.618", execution_id="exec-2")))
    suggestion = base.suggestions[0]
    assert suggestion.fact_ids == (base.facts[0].signature,)


# --- determinism / reproducibility -----------------------------------------


def test_same_input_same_everything() -> None:
    observations = (
        _obs("K.618", execution_id="a"),
        _obs("K.618", execution_id="b"),
        _obs("Ave Verum", field="title", execution_id="c"),
    )
    base1 = _mined(observations)
    base2 = _mined(observations)
    assert base1 == base2
    assert base1.facts == base2.facts
    assert base1.suggestions == base2.suggestions


def test_mining_does_not_modify_input() -> None:
    observations = (_obs("K.618", execution_id="a"), _obs("K.618", execution_id="b"))
    collector = DefaultKnowledgeCollector()
    base = collector.collect(observations)
    before = base
    _ = DefaultKnowledgeMiner().mine(base)
    assert base == before
    assert base.suggestions == ()


def test_reproducible_across_executions() -> None:
    obs_a = _base((_obs("K.618"), _obs("K.618", execution_id="e2")))
    obs_b = _base((_obs("K.618", execution_id="e2"), _obs("K.618")))
    assert DefaultKnowledgeMiner().mine(obs_a) == DefaultKnowledgeMiner().mine(obs_b)


# --- monotonicity ----------------------------------------------------------


def test_monotonicity_adds_facts_and_suggestions_never_removes() -> None:
    collector = DefaultKnowledgeCollector()
    miner = DefaultKnowledgeMiner()

    small = miner.mine(collector.collect((_obs("K.618", execution_id="e1"),)))
    assert small.facts and small.facts[0].count == 1
    assert small.suggestions == ()

    large = miner.mine(collector.collect((_obs("K.618", execution_id="e1"), _obs("K.618", execution_id="e2"))))
    # every fact of the small base survives, with a non-decreasing count.
    small_keys = {f.signature: f for f in small.facts}
    large_keys = {f.signature: f for f in large.facts}
    for key, fact in small_keys.items():
        assert key in large_keys
        assert large_keys[key].count >= fact.count
    # new suggestions may appear; existing keys never disappear.
    assert len(large.facts) >= len(small.facts)
    assert len(large.suggestions) >= len(small.suggestions)


# --- integration: Canonicalizer -> Matcher -> Ranking -> Merge -> Evidence -> Collector -> Miner --


def _descriptor(
    title: str,
    composer: str | None = None,
    catalogue: str | None = None,
    canonical_title: str | None = None,
    subtitle: str | None = None,
) -> WorkDescriptor:
    return WorkDescriptor(
        work_id=WorkId("work"),
        title=title,
        composer=composer,
        catalogue_number=catalogue,
        canonical_title=canonical_title,
        subtitle=subtitle,
    )


def _rep(
    pid: str,
    fmt: OutputFormat,
    title: str,
    composer: str | None = None,
    catalogue: str | None = None,
    canonical_title: str | None = None,
    confidence: float = 0.9,
    subtitle: str | None = None,
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{pid}-1"),
        work_descriptor=_descriptor(title, composer, catalogue, canonical_title, subtitle),
        provider_id=ProviderId(pid),
        format=fmt,
        confidence=Confidence(confidence),
    )


def test_integration_pipeline_produces_verifiable_suggestion() -> None:
    matcher = DefaultWorkMatcher(MatchingConfig())
    canonical = Canonicalizer(_RULES).canonicalize("K618")
    assert canonical.output == "KV 618"

    query = _descriptor(title="Ave Verum", composer="Mozart", catalogue=canonical.output)
    candidates = [
        _rep(
            "imslp",
            OutputFormat.MUSICXML,
            "Ave Verum Corpus",
            "Mozart",
            "KV 618",
            "Ave Verum Corpus",
            subtitle="Ave Verum Corpus, KV 618",
        ),
        _rep(
            "openscore",
            OutputFormat.MUSICXML,
            "Ave Verum Corpus",
            "Mozart",
            "KV 618",
            "Ave Verum Corpus",
            subtitle="Ave verum corpus",
        ),
    ]
    assert matcher.match(query, candidates[0].work_descriptor).level is MatchLevel.SAME
    assert matcher.match(candidates[0].work_descriptor, candidates[1].work_descriptor).level is MatchLevel.SAME

    group = WorkGroup(
        work=candidates[0].work_descriptor,
        representations=tuple(candidates),
        providers=tuple(ProviderId(c.provider_id.value) for c in candidates),
    )

    context = RankingContext(query_descriptor=query, user_preferences=UserPreferences())
    ranked = DefaultWorkRanker().rank((group,), context, RankingConfig())
    assert len(ranked.order) == 1

    merge = DefaultMergeService().merge(group, MergePolicy())
    assert merge.evidence  # Evidence produced by Merge

    observations = tuple(
        KnowledgeObservation(
            execution_id=execution_id,
            source=KnowledgeSource.MERGE,
            field=prov.field,
            value=str(prov.value),
            provider=prov.source,
        )
        for execution_id in ("exec-1", "exec-2")
        for prov in merge.provenance
    )
    assert observations

    base = DefaultKnowledgeCollector().collect(observations)
    mined = DefaultKnowledgeMiner().mine(base)

    assert mined.facts
    suggestion = next((s for s in mined.suggestions if s.field == "subtitle"), None)
    assert suggestion is not None
    assert suggestion.suggestion_type is KnowledgeSuggestionType.ADD_ALIAS
    assert suggestion.fact_ids  # traceable to the facts that support it

    # reproducible: mining the same base again yields identical results.
    assert DefaultKnowledgeMiner().mine(base) == mined
