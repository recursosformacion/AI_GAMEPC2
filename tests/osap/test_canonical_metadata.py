from src.osap.application.canonical_metadata import MetadataEnricher, normalize_genre
from src.osap.application.work_merge_service import WorkMergeService
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _candidate(
    cid: str, title: str, composer: str, provider: str, fmt: OutputFormat, meta: dict[str, object] | None = None
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=WorkDescriptor(work_id=WorkId(cid), title=title, composer=composer),
        provider_id=ProviderId(provider),
        format=fmt,
        confidence=Confidence(0.9),
        public_domain=True,
        metadata=meta or {},
    )


class TestNormalizeGenre:
    def test_mass_variants(self) -> None:
        assert normalize_genre("Mass") == "Mass"
        assert normalize_genre("Missa") == "Mass"
        assert normalize_genre("Messe") == "Mass"
        assert normalize_genre("motet") == "Motet"


class TestCanonicalComposer:
    def test_expands_initials_and_id(self) -> None:
        from src.osap.application.canonical_metadata import _canonical_composer

        comp = _canonical_composer("W.A. Mozart")
        assert comp.display_name == "Wolfgang Amadeus Mozart"
        assert comp.composer_id.startswith("c")
        assert "Wolfgang" in comp.display_name


class TestMetadataEnricher:
    def test_enrich_merges_fields(self) -> None:
        candidates = (
            _candidate(
                "a",
                "Ave Verum Corpus",
                "W.A. Mozart",
                "pdmx",
                OutputFormat.MUSICXML,
                {"genres": "Motet", "duration_seconds": 120},
            ),
            _candidate(
                "b", "Ave verum corpus, K.618", "Wolfgang Amadeus Mozart", "imslp", OutputFormat.PDF, {"voices": "SATB"}
            ),
        )
        group = WorkMergeService().group(candidates)[0]
        cw = MetadataEnricher().enrich(group)
        assert cw.catalog == "K 618"
        assert cw.composer is not None
        assert "Mozart" in cw.composer.display_name
        assert cw.genre == "Motet"
        assert cw.duration == 120.0
        assert len(cw.representations) == 2
        assert cw.public_domain is True
