"""Regression tests for focused search enrichment identity safeguards."""

from src.osap.api.platform._support import _title_core_match
from src.osap.application.metadata_normalizer import MetadataNormalizer


def _core(title: str, composer: str) -> set[str]:
    return set(MetadataNormalizer.comparison_title(title, composer).split())


def test_focused_enrichment_rejects_different_work_numbers() -> None:
    reference = "Violin Concerto No.3 in B-flat major"
    candidate = "Violin Concerto No.1 in F major"
    core = _core(reference, "Dieudonné-Pascal Pieltain")

    # comparison_title removes number and key, so a plain token-overlap check
    # would consider both works identical ("violin concerto").
    assert core == {"violin", "concerto"}
    assert not _title_core_match(core, candidate, reference_title=reference)


def test_focused_enrichment_keeps_same_number_across_editions() -> None:
    reference = "Violin Concerto No.3 in B-flat major"
    candidate = "Violin Concerto No.3 in B-flat major (parts)"
    core = _core(reference, "Dieudonné-Pascal Pieltain")

    assert _title_core_match(core, candidate, reference_title=reference)


def test_focused_enrichment_preserves_un-numbered_title_matching() -> None:
    reference = "Ave Verum Corpus"
    candidate = "Ave Verum Corpus a 4"
    core = _core(reference, "Wolfgang Amadeus Mozart")

    assert _title_core_match(core, candidate, reference_title=reference)
