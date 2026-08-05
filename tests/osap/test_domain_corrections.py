import tempfile
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from src.osap.application.canonical_metadata import MetadataEnricher
from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.work_merge_service import WorkGroup, WorkMergeService
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ResourceUnavailableError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.catalogs.pdmx.pdmx_catalog_provider import PdmxCatalogProvider


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
                _candidate("c1", "Piano Sonata No. 11 in A, K. 331", "Mozart", "pdmx"),
                _candidate("c2", "Symphony No. 5 in C minor, Op. 67", "Beethoven", "openscore"),
            )
        )
        # The catalogue is shown separately; the display title keeps the work
        # number and key but not the catalogue marker.
        titles = {g.work.title for g in groups}
        assert "Piano Sonata No. 11 in A" in titles
        assert "Symphony No. 5 in C Minor" in titles
        cats = {g.work.catalogue_number for g in groups}
        assert "K 331" in cats
        assert "Op. 67" in cats

    def test_display_title_is_never_normalized(self) -> None:
        service = WorkMergeService()
        groups = service.group((_candidate("c1", "Ave Verum Corpus (WIP)", "Mozart", "pdmx"),))
        work = groups[0].work
        assert "WIP" in work.title
        assert "WIP" not in (work.canonical_title or "")
        assert work.canonical_key == MetadataNormalizer.normalize(work.title, work.composer).signature()

    def test_best_title_wins_across_providers(self) -> None:
        # Two representations of the same work merge into ONE work; the display
        # title is the clean best-preference title and the catalogue is shown
        # separately (never embedded in the title).
        service = WorkMergeService()
        candidates = (
            _candidate("c1", "Ave Verum Corpus", "Mozart", "pdmx"),
            _candidate("c2", "Ave Verum Corpus, K. 618", "Wolfgang Amadeus Mozart", "imslp"),
        )
        groups = service.group(candidates)
        assert len(groups) == 1
        assert groups[0].work.title == "Ave Verum Corpus"
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


class TestPdmxSpecificStatus:
    """Correction 7: PDMX distinguishes fine-grained reasons, never just UNAVAILABLE."""

    def _provider(self, index_path: Path | None = None, download_base: str | None = None) -> PdmxCatalogProvider:
        return PdmxCatalogProvider(
            csv_url="",
            index_path=index_path,
            local_csv=None,
            download_base=download_base,
        )

    def test_index_missing_raises_with_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = self._provider(index_path=Path(tmp) / "missing.db")
            with pytest.raises(ResourceUnavailableError) as exc:
                provider.search(_request())
            assert exc.value.code == "index_missing"

    def test_mirror_not_configured_code(self) -> None:
        from src.osap.infrastructure.catalogs.pdmx.pdmx_catalog_provider import PdmxUnavailableReason

        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "idx.db"
            provider = self._provider(index_path=index, download_base=None)
            candidate = _candidate("c1", "Ave Verum Corpus", "Mozart", "pdmx")
            candidate = _with_path(candidate, "./mxl/0/0/0/ave.mxl")
            with pytest.raises(ResourceUnavailableError) as exc:
                provider.download(candidate)
            assert exc.value.code == PdmxUnavailableReason.MIRROR_NOT_CONFIGURED.value

    def test_download_unsupported_code(self) -> None:
        provider = self._provider()
        with pytest.raises(ResourceUnavailableError) as exc:
            provider.download(_candidate("c1", "Ave Verum Corpus", "Mozart", "pdmx"))
        assert exc.value.code == "download_unsupported"

    def test_network_error_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.infrastructure.catalogs.pdmx.pdmx_catalog_provider import PdmxUnavailableReason

        def boom(url: str, timeout: int) -> None:  # noqa: ARG002
            raise OSError("net down")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        with tempfile.TemporaryDirectory() as tmp:
            provider = self._provider(index_path=Path(tmp) / "idx.db", download_base="https://mirror")
            with pytest.raises(ResourceUnavailableError) as exc:
                provider.download(_with_path(_candidate("c1", "Ave Verum Corpus", "Mozart", "pdmx"), "./mxl/a.mxl"))
            assert exc.value.code == PdmxUnavailableReason.NETWORK_ERROR.value

    def test_index_available_status(self) -> None:
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "idx.db"
            conn = sqlite3.connect(index)
            conn.close()
            provider = self._provider(index_path=index)
            assert provider.availability().value == "index_available"
            caps = provider.capabilities()
            assert caps.metadata.get("index_available") is True


class TestPdmxAutoBuild:
    """PDMX auto-builds its index on first search when a source is available."""

    def test_search_builds_index_from_local_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "pdmx.csv"
        csv_file.write_text(
            "title,composer_name,license_conflict,rating,mxl,pdf,mid\n"
            "Ave Verum Corpus,Wolfgang Amadeus Mozart,False,4.5,./mxl/a.mxl,,\n",
            encoding="utf-8",
        )
        index = tmp_path / "index.db"
        provider = PdmxCatalogProvider(csv_url="", index_path=index, local_csv=csv_file)
        assert not index.exists()
        candidates = provider.search(_request())
        assert index.exists()
        assert any(c.work_descriptor.title == "Ave Verum Corpus" for c in candidates)

    def test_search_without_source_stays_missing(self, tmp_path: Path) -> None:
        provider = PdmxCatalogProvider(csv_url="", index_path=Path(tmp_path) / "missing.db", local_csv=None)
        with pytest.raises(ResourceUnavailableError) as exc:
            provider.search(_request())
        assert exc.value.code == "index_missing"


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


def _request() -> ResolveRequest:
    return ResolveRequest(title="Ave Verum")


def _with_path(candidate: CandidateRepresentation, path: str) -> CandidateRepresentation:
    return replace(candidate, metadata={**candidate.metadata, "path": path})
