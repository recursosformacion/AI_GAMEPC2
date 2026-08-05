"""Pruebas del AcquisitionResolver (cómo adquirir cada representación)."""

from pathlib import Path

from src.osap.application.acquisition import AcquisitionMethod, AcquisitionResolver
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _rep(
    provider: str,
    fmt: OutputFormat = OutputFormat.MUSICXML,
    downloadable: bool = True,
    manual_download: bool = False,
    url: str | None = None,
    local_path: str | None = None,
    notes: str | None = None,
    reason: str | None = None,
) -> CandidateRepresentation:
    metadata: dict[str, object] = {}
    if reason:
        metadata["acquisition_reason"] = reason
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{provider}-1"),
        work_descriptor=WorkDescriptor(work_id=WorkId("w"), title="Ave Verum Corpus", composer="Mozart"),
        provider_id=ProviderId(provider),
        format=fmt,
        confidence=Confidence(0.8),
        downloadable=downloadable,
        manual_download=manual_download,
        download_url=url,
        local_path=local_path,
        notes=notes,
        metadata=metadata,
    )


class TestAcquisitionResolver:
    def test_local(self, tmp_path: Path) -> None:
        local = tmp_path / "ave.mxl"
        local.write_bytes(b"<score/>")
        info = AcquisitionResolver().resolve(_rep("local", local_path=str(local)))
        assert info.method is AcquisitionMethod.LOCAL
        assert info.local_path == str(local)

    def test_direct(self) -> None:
        info = AcquisitionResolver().resolve(_rep("pdmx", url="https://mirror.example.com/mxl/a.mxl"))
        assert info.method is AcquisitionMethod.DIRECT
        assert info.url == "https://mirror.example.com/mxl/a.mxl"

    def test_external_imslp(self) -> None:
        info = AcquisitionResolver().resolve(
            _rep("imslp", OutputFormat.PDF, downloadable=False, manual_download=True, url="https://imslp.org/wiki/Ave")
        )
        assert info.method is AcquisitionMethod.EXTERNAL
        assert info.url == "https://imslp.org/wiki/Ave"

    def test_manual_pdmx_sin_mirror(self) -> None:
        info = AcquisitionResolver().resolve(_rep("pdmx", downloadable=False, reason="mirror_not_configured"))
        assert info.method is AcquisitionMethod.MANUAL
        assert info.reason == "mirror_not_configured"

    def test_unavailable(self) -> None:
        info = AcquisitionResolver().resolve(_rep("foo", downloadable=False))
        assert info.method is AcquisitionMethod.UNAVAILABLE
