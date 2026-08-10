from dataclasses import replace
from typing import Any

import pytest

from src.osap.application.canonical_metadata import MetadataEnricher
from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.work_merge_service import WorkGroup, WorkMergeService
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _candidate(cid: str, title: str, composer: str, provider: str) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=WorkDescriptor(work_id=WorkId(cid), title=title, composer=composer),
        provider_id=ProviderId(provider),
        format=OutputFormat.MUSICXML,
        confidence=Confidence(0.9),
    )


class TestDisplayVsCanonical:
    """Corrections 1-3: normalization never modifies the visible title."""

    def test_display_title_preserves_catalogue_markers(self) -> None:
        service = WorkMergeService()
        groups = service.group(
            (
                _candidate("c1", "Piano Sonata No. 11 in A, K. 331", "Mozart", "omr"),
                _candidate("c2", "Symphony No. 5 in C minor, Op. 67", "Beethoven", "openscore"),
            )
        )
        # El título de pantalla es el primer título que compone la fusión, conservando
        # el catálogo/Op. (también se expone por separado en catalogue_number).
        titles = {g.work.title for g in groups}
        assert any("K. 331" in t for t in titles)
        assert any("Op. 67" in t for t in titles)
        cats = {g.work.catalogue_number for g in groups}
        assert "K 331" in cats
        assert "Op. 67" in cats

    def test_display_title_is_never_normalized(self) -> None:
        service = WorkMergeService()
        groups = service.group((_candidate("c1", "Ave Verum Corpus (WIP)", "Mozart", "omr"),))
        work = groups[0].work
        assert "WIP" in work.title
        assert "WIP" not in (work.canonical_title or "")
        assert work.canonical_key == MetadataNormalizer.normalize(work.title, work.composer).signature()

    def test_best_title_wins_across_providers(self) -> None:
        # Dos representaciones de la misma obra se fusionan en UNA; el título de
        # pantalla es el primer título (mejor preferencia) y conserva el catálogo.
        service = WorkMergeService()
        candidates = (
            _candidate("c1", "Ave Verum Corpus", "Mozart", "omr"),
            _candidate("c2", "Ave Verum Corpus, K. 618", "Wolfgang Amadeus Mozart", "imslp"),
        )
        groups = service.group(candidates)
        assert len(groups) == 1
        assert "Ave Verum Corpus" in groups[0].work.title
        assert "K. 618" in groups[0].work.title
        assert groups[0].work.catalogue_number == "K 618"


class TestPublicDomainTriState:
    """Correction 6: Sí/No/Desconocido; never deduce No from absence."""

    def _group(self, pd_values: list[bool | None]) -> WorkGroup:
        candidates = tuple(
            _with_pd(_candidate(f"c{i}", "Ave Verum Corpus", "Mozart", f"p{i}"), value)
            for i, value in enumerate(pd_values)
        )
        return WorkMergeService().group(candidates)[0]

    def test_all_unknown_is_unknown(self) -> None:
        cw = MetadataEnricher().enrich(self._group([None, None]))
        assert cw.public_domain is None

    def test_any_true_is_true(self) -> None:
        cw = MetadataEnricher().enrich(self._group([None, True, None]))
        assert cw.public_domain is True

    def test_explicit_false_is_false(self) -> None:
        cw = MetadataEnricher().enrich(self._group([False, None]))
        assert cw.public_domain is False


def _with_pd(candidate: CandidateRepresentation, value: bool | None) -> CandidateRepresentation:
    return replace(candidate, public_domain=value)


class TestMediaWikiNetworkErrors:
    """IMSLP network failures become MediaWikiError (ScoreResolutionError) so
    the engine marks the provider unavailable instead of aborting resolution."""

    def test_get_network_error_raises_mediawiki_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error

        from src.osap.infrastructure.mediawiki import MediaWikiClient
        from src.osap.infrastructure.mediawiki.mw_client import MediaWikiError

        def boom(*args: object, **kwargs: object) -> None:  # noqa: ARG001, ARG002
            raise urllib.error.URLError("network down")

        client = MediaWikiClient()
        monkeypatch.setattr(urllib.request, "urlopen", boom)
        with pytest.raises(MediaWikiError):
            client._get({"action": "query"})

    def test_download_network_error_raises_mediawiki_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error

        from src.osap.infrastructure.mediawiki import MediaWikiClient
        from src.osap.infrastructure.mediawiki.mw_client import MediaWikiError

        def boom(*args: object, **kwargs: object) -> None:  # noqa: ARG001, ARG002
            raise TimeoutError("timed out")

        client = MediaWikiClient()
        monkeypatch.setattr(urllib.request, "urlopen", boom)
        with pytest.raises(MediaWikiError):
            client.download("https://imslp.org/example.pdf")


class TestRepresentationInfoPreserved:
    """Correction 5: representations keep ALL their info through the merge."""

    def _candidate(self, **overrides: Any) -> CandidateRepresentation:
        base = CandidateRepresentation(
            candidate_id=CandidateId("c1"),
            work_descriptor=WorkDescriptor(work_id=WorkId("w"), title="Ave Verum Corpus", composer="Mozart"),
            provider_id=ProviderId("imslp"),
            format=OutputFormat.PDF,
        )
        return replace(base, **overrides)

    def test_merge_preserves_download_url_and_manual_info(self) -> None:
        from src.osap.application.canonical_metadata import MetadataEnricher

        c = self._candidate(
            downloadable=False,
            manual_download=True,
            download_url="https://imslp.org/wiki/Ave_Verum_Corpus",
            remote_id="page42",
            rating=3.5,
            notes="anti-bot",
            license="public domain",
        )
        group = WorkMergeService().group((c,))[0]
        cw = MetadataEnricher().enrich(group)
        rep = cw.representations[0]
        assert rep.downloadable is False
        assert rep.manual_download is True
        assert rep.download_url == "https://imslp.org/wiki/Ave_Verum_Corpus"
        assert rep.remote_id == "page42"
        assert rep.rating == 3.5
        assert rep.notes == "anti-bot"
        assert rep.license == "public domain"
