"""Regresión de fusión por fallback de título (WorkGroupingMatcher).

Caso Chopin: tres Preludios del Op. 28 con catálogo/número/clave distintos NO deben
fusionarse aunque el título reducido coincida en 'prelude'. La fusión por título solo
aplica con título específico (>=3 tokens) o cuando no hay contradicción estructurada.
"""

from src.osap.application.work_grouping_matcher import MergeVerdict, WorkGroupingMatcher
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

_matcher = WorkGroupingMatcher()


def _cand(title: str, composer: str | None) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(title),
        work_descriptor=WorkDescriptor(work_id=WorkId(title), title=title, composer=composer),
        provider_id=ProviderId("omr"),
        format=OutputFormat.MUSICXML,
        origin="test",
        confidence=Confidence(0.9),
    )


def test_chopin_preludes_not_merged() -> None:
    a = _cand("Prelude in E-flat minor", "Chopin")
    b = _cand("Chopin Prelude Op. 28 No. 24", "Chopin")
    c = _cand("Frédéric Chopin: Prelude in G major Op.28 No.3", "Frédéric Chopin")

    for x, y in ((a, b), (a, c), (b, c)):
        d = _matcher.compare(x, y)
        assert d.decision is MergeVerdict.NOT_MERGED, f"fusionó: {x.work_descriptor.title} vs {y.work_descriptor.title}"


def test_same_catalog_merges() -> None:
    a = _cand("Ave Verum, KV 618", "Mozart")
    b = _cand("Ave Verum Corpus K 618 - Wolfgang Amadeus Mozart", "Wolfgang Amadeus Mozart")
    d = _matcher.compare(a, b)
    assert d.decision is MergeVerdict.MERGED


def test_ave_verum_corpus_specific_title_merges_without_catalog() -> None:
    a = _cand("Ave Verum Corpus", "Mozart")
    b = _cand("Ave Verum Corpus, K. 618", "Mozart")
    d = _matcher.compare(a, b)
    assert d.decision is MergeVerdict.MERGED
