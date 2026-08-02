import json
from pathlib import Path

from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.infrastructure.catalogs.local import LocalCatalogProvider


def _write_work(root: Path, folder: str, title: str, composer: str | None, fmt: str = ".mxl") -> None:
    dir_path = root / folder
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "work.json").write_text(
        json.dumps({"title": title, "composer": composer, "work_id": {"value": "w-" + folder}}),
        encoding="utf-8",
    )
    (dir_path / f"score{fmt}").write_bytes(b"SCORE-BYTES")


class TestLocalCatalogProvider:
    def test_no_library_returns_no_result(self, tmp_path: Path) -> None:
        provider = LocalCatalogProvider(tmp_path / "missing")
        assert provider.search(ResolveRequest(title="Ave Maria")) == ()

    def test_empty_library_returns_no_result(self, tmp_path: Path) -> None:
        tmp_path.mkdir(parents=True, exist_ok=True)
        provider = LocalCatalogProvider(tmp_path)
        assert provider.search(ResolveRequest(title="Ave Maria")) == ()

    def test_finds_work_by_title(self, tmp_path: Path) -> None:
        _write_work(tmp_path, "Ave_Maria", "Ave Maria", "Franz Schubert")
        provider = LocalCatalogProvider(tmp_path)
        candidates = provider.search(ResolveRequest(title="Ave Maria"))
        assert len(candidates) == 1
        assert candidates[0].work_descriptor.title == "Ave Maria"
        assert candidates[0].format == OutputFormat.MUSICXML
        assert candidates[0].local_path is not None

    def test_finds_work_by_composer(self, tmp_path: Path) -> None:
        _write_work(tmp_path, "Ave_Maria", "Ave Maria", "Franz Schubert")
        provider = LocalCatalogProvider(tmp_path)
        candidates = provider.search(ResolveRequest(composer="Schubert"))
        assert len(candidates) == 1

    def test_no_match(self, tmp_path: Path) -> None:
        _write_work(tmp_path, "Ave_Maria", "Ave Maria", "Franz Schubert")
        provider = LocalCatalogProvider(tmp_path)
        assert provider.search(ResolveRequest(title="Sinfonia")) == ()

    def test_download_reads_local_file(self, tmp_path: Path) -> None:
        _write_work(tmp_path, "Ave_Maria", "Ave Maria", "Franz Schubert")
        provider = LocalCatalogProvider(tmp_path)
        candidate = provider.search(ResolveRequest(title="Ave Maria"))[0]
        acquisition = provider.download(candidate)
        assert acquisition.source.content == b"SCORE-BYTES"
        assert acquisition.source.format == OutputFormat.MUSICXML
