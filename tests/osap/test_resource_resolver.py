"""Pruebas del ResourceResolver (Work → Resource → Representation)."""

from src.osap.application.resource_resolver import ResolvedWork, ResourceResolver
from src.osap.application.work_merge_service import WorkMergeService
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _rep(
    cid: str,
    title: str,
    composer: str,
    provider: str,
    fmt: OutputFormat = OutputFormat.MUSICXML,
    downloadable: bool = True,
    manual_download: bool = False,
    url: str | None = None,
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(cid),
        work_descriptor=WorkDescriptor(work_id=WorkId(cid), title=title, composer=composer),
        provider_id=ProviderId(provider),
        format=fmt,
        confidence=Confidence(0.8),
        downloadable=downloadable,
        manual_download=manual_download,
        download_url=url,
    )


def _resolve(candidates: tuple[CandidateRepresentation, ...]) -> ResolvedWork:
    group = WorkMergeService().group(candidates)[0]
    return ResourceResolver().resolve(group)


class TestResourceResolver:
    def test_groups_by_format(self) -> None:
        rw = _resolve(
            (
                _rep("a", "Ave Verum Corpus", "Mozart", "pdmx", OutputFormat.MUSICXML),
                _rep(
                    "b",
                    "Ave Verum Corpus",
                    "Mozart",
                    "imslp",
                    OutputFormat.PDF,
                    downloadable=False,
                    manual_download=True,
                ),
            )
        )
        assert len(rw.resources) == 2
        fmts = {r.format for r in rw.resources}
        assert {"musicxml", "pdf"} == fmts
        # musicxml primero (orden: score antes que audio; musicxml antes que pdf)
        assert rw.resources[0].format == "musicxml"

    def test_best_composer_is_clean(self) -> None:
        # El compositor de una rep es ruido ("KV 618 - W. A. Mozart"); debe
        # resolverse al mejor disponible (canónico).
        rw = _resolve(
            (
                _rep("a", "Ave Verum Corpus", "KV 618 - W. A. Mozart", "pdmx"),
                _rep("b", "Ave Verum Corpus", "Wolfgang Amadeus Mozart", "openscore"),
            )
        )
        assert rw.composer == "Wolfgang Amadeus Mozart"

    def test_manual_vs_directa(self) -> None:
        rw = _resolve(
            (
                _rep("a", "Ave Verum Corpus", "Mozart", "pdmx", OutputFormat.MUSICXML),
                _rep(
                    "b",
                    "Ave Verum Corpus",
                    "Mozart",
                    "imslp",
                    OutputFormat.PDF,
                    downloadable=False,
                    manual_download=True,
                    url="https://imslp.org/wiki/Ave",
                ),
            )
        )
        musicxml = next(r for r in rw.resources if r.format == "musicxml")
        pdf = next(r for r in rw.resources if r.format == "pdf")
        assert musicxml.downloadable is True
        assert musicxml.manual is False
        assert pdf.downloadable is False
        assert pdf.manual is True
        assert pdf.best is not None
        assert pdf.best.download_url == "https://imslp.org/wiki/Ave"

    def test_selects_directa_over_manual_in_same_format(self) -> None:
        # Entre dos MusicXML, se elige la directa (OpenScore) aunque la otra sea PDMX.
        rw = _resolve(
            (
                _rep(
                    "a",
                    "Ave Verum Corpus",
                    "Mozart",
                    "pdmx",
                    OutputFormat.MUSICXML,
                    downloadable=False,
                    manual_download=True,
                ),
                _rep("b", "Ave Verum Corpus", "Mozart", "openscore", OutputFormat.MUSICXML, downloadable=True),
            )
        )
        musicxml = next(r for r in rw.resources if r.format == "musicxml")
        assert musicxml.downloadable is True
        assert musicxml.best is not None
        assert musicxml.best.provider_id.value == "openscore"

    def test_has_direct_download(self) -> None:
        rw = _resolve(
            (
                _rep("a", "Ave Verum Corpus", "Mozart", "pdmx", OutputFormat.MUSICXML),
                _rep(
                    "b",
                    "Ave Verum Corpus",
                    "Mozart",
                    "imslp",
                    OutputFormat.PDF,
                    downloadable=False,
                    manual_download=True,
                ),
            )
        )
        assert rw.has_direct_download is True

    def test_no_direct_download_reports_manual(self) -> None:
        rw = _resolve(
            (
                _rep(
                    "a",
                    "Ave Verum Corpus",
                    "Mozart",
                    "imslp",
                    OutputFormat.PDF,
                    downloadable=False,
                    manual_download=True,
                    url="https://imslp.org/wiki/Ave",
                ),
            )
        )
        assert rw.has_direct_download is False
        pdf = rw.resources[0]
        assert pdf.manual is True
        assert pdf.best is not None and pdf.best.download_url
