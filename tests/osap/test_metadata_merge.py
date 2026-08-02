from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.work_merge_service import WorkMergeService
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


class TestMetadataNormalizer:
    def test_canonical_composer_expands(self) -> None:
        assert MetadataNormalizer.canonical_composer("W.A. Mozart") == "Wolfgang Amadeus Mozart"
        assert MetadataNormalizer.canonical_composer("Mozart (1756-1791)") == "Wolfgang Amadeus Mozart"

    def test_split_roles(self) -> None:
        roles = MetadataNormalizer.split_roles("Wolfgang Amadeus Mozart Arr. Henry Miller")
        assert roles.get("composer") == "Wolfgang Amadeus Mozart"
        assert "Henry Miller" in roles.get("arranger", "")

    def test_clean_title(self) -> None:
        clean, meta = MetadataNormalizer.clean_title("Ave Verum Corpus (WIP)")
        assert "WIP" not in clean
        clean2, meta2 = MetadataNormalizer.clean_title("Clarinet Concerto in A for Piano")
        assert meta2.get("instrumentation") == "Piano"
        assert "for Piano" not in clean2

    def test_catalogue_extraction(self) -> None:
        clean, meta = MetadataNormalizer.clean_title("Requiem KV626")
        assert meta.get("catalogue") == "KV 626"

    def test_work_key(self) -> None:
        a = MetadataNormalizer.work_key("Ave Verum Corpus", "W.A. Mozart")
        b = MetadataNormalizer.work_key("Ave verum corpus (WIP)", "Mozart")
        assert a == b


def _candidate(cid: str, title: str, composer: str, provider: str) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=WorkDescriptor(work_id=WorkId(cid), title=title, composer=composer),
        provider_id=ProviderId(provider),
        format=OutputFormat.MUSICXML,
    )


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
        # The normalizer never touches the visible title: it only produces the
        # internal canonical_title / canonical_key used for comparison.
        service = WorkMergeService()
        candidates = (_candidate("c1", "Ave Verum Corpus (WIP)", "Mozart", "pdmx"),)
        groups = service.group(candidates)
        assert "WIP" in groups[0].work.title  # display title keeps the noise
        assert "WIP" not in (groups[0].work.canonical_title or "")
        assert groups[0].work.canonical_key is not None
        assert groups[0].work.composer == "Wolfgang Amadeus Mozart"
