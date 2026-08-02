from pathlib import Path

import pytest

from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import SourceId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.adapters.library.local import LocalLibrary

WORK = WorkDescriptor(work_id=WorkId("w1"), title="Canço de Comiat", composer="Eduard Toldrà")


def _source(format: OutputFormat = OutputFormat.MUSICXML, content: bytes = b"<score/>") -> MusicalSource:
    return MusicalSource(SourceId("s1"), content, format)


class TestLocalLibrary:
    def test_save_and_exists(self, tmp_path: Path) -> None:
        library = LocalLibrary(tmp_path)
        library.save(_source(), "Canço de Comiat")
        assert library.exists("Canço de Comiat")
        assert (tmp_path / "Canço_de_Comiat.mxl").read_bytes() == b"<score/>"

    def test_list_and_remove(self, tmp_path: Path) -> None:
        library = LocalLibrary(tmp_path)
        library.save(_source(), "uno")
        library.save(_source(), "dos")
        assert set(library.list()) == {"uno", "dos"}
        library.remove("uno")
        assert set(library.list()) == {"dos"}

    def test_store_work_creates_folder(self, tmp_path: Path) -> None:
        library = LocalLibrary(tmp_path)
        library.store_work(WORK, _source(), {"provider": "imslp"}, "Canço de Comiat")
        folder = library.work_dir("Canço de Comiat")
        assert (folder / "score.mxl").read_bytes() == b"<score/>"
        assert (folder / "work.json").exists()
        assert library.exists("Canço de Comiat")

    def test_non_bytes_raises(self, tmp_path: Path) -> None:
        library = LocalLibrary(tmp_path)
        source = MusicalSource(SourceId("s1"), {"not": "bytes"}, OutputFormat.MUSICXML)
        with pytest.raises(ScoreResolutionError):
            library.save(source, "obra")
