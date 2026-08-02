import json
import re
from dataclasses import asdict
from pathlib import Path

from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import LibraryId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.library_provider import ILibraryProvider

_EXTENSION_BY_FORMAT: dict[OutputFormat, str] = {
    OutputFormat.MUSICXML: ".mxl",
    OutputFormat.MEI: ".mei",
    OutputFormat.MIDI: ".mid",
    OutputFormat.PDF: ".pdf",
    OutputFormat.JSON: ".json",
    OutputFormat.SCORE: ".xml",
}


class LocalLibrary(ILibraryProvider):
    """Stores resolved works in a local directory.

    Flat saves go to ``<root>/<name>.<ext>``. Work storage creates a folder
    per work preserving full provenance::

        <root>/Canço_de_Comiat/
            metadata.json
            work.json
            acquisition.json
            score.musicxml
            source.json
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def library_id(self) -> LibraryId:
        return LibraryId("local")

    @property
    def root(self) -> Path:
        return self._root

    def save(self, source: MusicalSource, identifier: str) -> None:
        if not isinstance(source.content, bytes):
            raise ScoreResolutionError("LocalLibrary only stores byte content")
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._path(identifier, source.format)
        target.write_bytes(source.content)

    def store_work(
        self, work: WorkDescriptor, source: MusicalSource, metadata: dict[str, object], identifier: str
    ) -> None:
        if not isinstance(source.content, bytes):
            raise ScoreResolutionError("LocalLibrary only stores byte content")
        folder = self._root / self._sanitize(identifier)
        folder.mkdir(parents=True, exist_ok=True)
        extension = _EXTENSION_BY_FORMAT.get(source.format, "")
        (folder / f"score{extension}").write_bytes(source.content)
        (folder / "work.json").write_text(
            json.dumps(asdict(work), default=str, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (folder / "metadata.json").write_text(
            json.dumps(metadata, default=str, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (folder / "acquisition.json").write_text(
            json.dumps({"format": source.format.value}, indent=2), encoding="utf-8"
        )
        (folder / "source.json").write_text(
            json.dumps({"source_url": source.metadata.get("source_url")}, indent=2), encoding="utf-8"
        )

    def exists(self, identifier: str) -> bool:
        stem = self._sanitize(identifier)
        if any(self._root.glob(f"{stem}.*")):
            return True
        return (self._root / stem).is_dir()

    def update(self, source: MusicalSource, identifier: str) -> None:
        self.remove(identifier)
        self.save(source, identifier)

    def remove(self, identifier: str) -> None:
        stem = self._sanitize(identifier)
        for match in self._root.glob(f"{stem}.*"):
            match.unlink()
        folder = self._root / stem
        if folder.is_dir():
            for child in folder.iterdir():
                child.unlink()
            folder.rmdir()

    def list(self) -> tuple[str, ...]:
        if not self._root.exists():
            return ()
        names = {p.stem for p in self._root.iterdir() if p.is_file()}
        names.update(p.name for p in self._root.iterdir() if p.is_dir())
        return tuple(sorted(names))

    def path_for(self, source: MusicalSource, identifier: str) -> Path:
        return self._path(identifier, source.format)

    def work_dir(self, identifier: str) -> Path:
        return self._root / self._sanitize(identifier)

    def _path(self, identifier: str, format: OutputFormat) -> Path:
        extension = _EXTENSION_BY_FORMAT.get(format, "")
        return self._root / f"{self._sanitize(identifier)}{extension}"

    @staticmethod
    def _sanitize(identifier: str) -> str:
        cleaned = re.sub(r"[^\w.\-]+", "_", identifier)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_. ")
        if not cleaned:
            raise ScoreResolutionError("Could not build a safe file name from the identifier")
        return cleaned
