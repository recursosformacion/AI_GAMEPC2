from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.work_grouping_matcher import (
    CatalogEquivalent,
    WorkGroupingMatcher,
)
from src.osap.application.work_merge_service import WorkMergeService
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


class TestMetadataNormalizer:
    def test_canonical_composer_expands(self) -> None:
        assert MetadataNormalizer.canonical_composer("W.A. Mozart") == "Wolfgang Amadeus Mozart"
        assert MetadataNormalizer.canonical_composer("Mozart (1756-1791)") == "Wolfgang Amadeus Mozart"

    def test_normalize_is_comparison_only(self) -> None:
        nm = MetadataNormalizer.normalize("Ave verum corpus, K.618 (Mozart)", "Wolfgang Amadeus Mozart")
        assert nm.normalized_title == "ave verum corpus"
        assert nm.normalized_composer == "wolfgang amadeus mozart"
        assert nm.normalized_catalog == "k 618"

    def test_work_key_is_removed(self) -> None:
        assert not hasattr(MetadataNormalizer, "work_key")
        assert not hasattr(MetadataNormalizer, "clean_title")


def _candidate(cid: str, title: str, composer: str, provider: str) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=WorkDescriptor(work_id=WorkId(cid), title=title, composer=composer),
        provider_id=ProviderId(provider),
        format=OutputFormat.MUSICXML,
    )


class TestWorkMatcher:
    def test_same_work_variants_merge(self) -> None:
        matcher = WorkGroupingMatcher()
        decision = matcher.compare(
            _candidate("c1", "Ave Verum Corpus", "W.A. Mozart", "pdmx"),
            _candidate("c2", "Ave verum corpus, K.618", "Wolfgang Amadeus Mozart", "imslp"),
        )
        assert decision.merged
        assert decision.decision.value == "MERGED"
        assert decision.score >= 0.5
        labels = decision.evidence_labels()
        assert {"composer", "title_similarity"} <= set(labels)

    def test_embedded_composer_merges(self) -> None:
        # El compositor incrustado en el título ("W. A. Mozart") no debe impedir la fusión.
        matcher = WorkGroupingMatcher()
        decision = matcher.compare(
            _candidate("c1", "Ave Verum Corpus", "Wolfgang Amadeus Mozart", "omr"),
            _candidate("c2", "Ave Verum Corpus W. A. Mozart (K. 618)", "Wolfgang Amadeus Mozart", "imslp"),
        )
        assert decision.merged
        assert decision.score >= 0.5

    def test_catalog_equivalent_evidence(self) -> None:
        matcher = WorkGroupingMatcher()
        decision = matcher.compare(
            _candidate("c1", "Ave Verum Corpus K.618", "Mozart", "pdmx"),
            _candidate("c2", "Ave verum corpus KV 618", "Mozart", "imslp"),
        )
        assert decision.merged
        catalogs = [e for e in decision.evidence if isinstance(e, CatalogEquivalent)]
        assert catalogs
        assert catalogs[0].normalized == "k 618"
        assert catalogs[0].weight == 0.2

    def test_distinct_sonatas_do_not_merge(self) -> None:
        matcher = WorkGroupingMatcher()
        decision = matcher.compare(
            _candidate("c1", "Piano Sonata No.11 in A, K.331", "Mozart", "pdmx"),
            _candidate("c2", "Piano Sonata No.12 in F, K.332", "Mozart", "pdmx"),
        )
        assert not decision.merged
        assert decision.decision.value == "NOT_MERGED"
        assert "catalog" not in decision.reason_labels()  # disagreeing catalog is a discriminator

    def test_different_composers_do_not_merge(self) -> None:
        matcher = WorkGroupingMatcher()
        decision = matcher.compare(
            _candidate("c1", "Ave Maria", "Gounod", "pdmx"),
            _candidate("c2", "Ave Maria", "Franz Schubert", "pdmx"),
        )
        assert not decision.merged

    def test_decision_has_work_key_and_id(self) -> None:
        matcher = WorkGroupingMatcher()
        decision = matcher.compare(
            _candidate("c1", "Ave Verum Corpus", "W.A. Mozart", "pdmx"),
            _candidate("c2", "Ave verum corpus, K.618", "Wolfgang Amadeus Mozart", "imslp"),
        )
        assert decision.work_key
        assert decision.work_id
        assert decision.work_id.startswith("work-")


class TestWorkMergeService:
    def test_groups_equivalent_works(self) -> None:
        service = WorkMergeService()
        candidates = (
            _candidate("c1", "Ave Verum Corpus", "W.A. Mozart", "pdmx"),
            _candidate("c2", "Ave verum corpus (WIP)", "Mozart", "imslp"),
            _candidate("c3", "Requiem", "Mozart", "openscore"),
        )
        groups = service.group(candidates)
        assert len(groups) == 2
        ave = next(g for g in groups if "Ave" in g.work.title)
        assert len(ave.representations) == 2
        assert {r.provider_id.value for r in ave.representations} == {"pdmx", "imslp"}

    def test_display_title_is_never_normalized(self) -> None:
        service = WorkMergeService()
        candidates = (_candidate("c1", "Ave Verum Corpus (WIP)", "Mozart", "pdmx"),)
        groups = service.group(candidates)
        assert "WIP" in groups[0].work.title  # display title keeps the noise
        assert "WIP" not in (groups[0].work.canonical_title or "")
        assert groups[0].work.canonical_key is not None
        assert groups[0].work.composer == "Wolfgang Amadeus Mozart"

    def test_catalogue_kept_separate(self) -> None:
        service = WorkMergeService()
        groups = service.group(
            (
                _candidate("c1", "Ave Verum Corpus", "Mozart", "pdmx"),
                _candidate("c2", "Ave verum corpus K.618", "Mozart", "pdmx"),
            )
        )
        assert len(groups) == 1
        assert groups[0].work.catalogue_number == "K 618"
