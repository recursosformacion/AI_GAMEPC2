import tempfile
import urllib.request
from dataclasses import replace
from pathlib import Path

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
        titles = {g.work.title for g in groups}
        assert "Piano Sonata No. 11 in A, K. 331" in titles
        assert "Symphony No. 5 in C minor, Op. 67" in titles

    def test_display_title_is_never_normalized(self) -> None:
        service = WorkMergeService()
        groups = service.group((_candidate("c1", "Ave Verum Corpus (WIP)", "Mozart", "pdmx"),))
        work = groups[0].work
        assert "WIP" in work.title
        assert "WIP" not in (work.canonical_title or "")
        assert work.canonical_key == MetadataNormalizer.work_key(work.title, work.composer)

    def test_best_title_wins_across_providers(self) -> None:
        # Two representations of the same work: the longer/more complete raw
        # title is chosen for display; never the normalized one.
        service = WorkMergeService()
        candidates = (
            _candidate("c1", "Ave Verum Corpus", "Mozart", "pdmx"),
            _candidate("c2", "Ave Verum Corpus, K. 618", "Wolfgang Amadeus Mozart", "imslp"),
        )
        groups = service.group(candidates)
        assert len(groups) == 1
        assert groups[0].work.title == "Ave Verum Corpus, K. 618"


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


def _request() -> ResolveRequest:
    return ResolveRequest(title="Ave Verum")


def _with_path(candidate: CandidateRepresentation, path: str) -> CandidateRepresentation:
    return replace(candidate, metadata={**candidate.metadata, "path": path})
