from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.value_objects import LibraryId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.library_provider import ILibraryProvider


class LibraryManager:
    """Facade over ILibraryProvider adapters. Dispatches operations to a library."""

    def __init__(self, libraries: tuple[ILibraryProvider, ...]) -> None:
        self._libraries = libraries

    def save(self, library_id: LibraryId, source: MusicalSource, identifier: str) -> None:
        self._find(library_id).save(source, identifier)

    def store_work(
        self,
        library_id: LibraryId,
        work: WorkDescriptor,
        source: MusicalSource,
        metadata: dict[str, object],
        identifier: str,
    ) -> None:
        self._find(library_id).store_work(work, source, metadata, identifier)

    def exists(self, library_id: LibraryId, identifier: str) -> bool:
        return self._find(library_id).exists(identifier)

    def update(self, library_id: LibraryId, source: MusicalSource, identifier: str) -> None:
        self._find(library_id).update(source, identifier)

    def remove(self, library_id: LibraryId, identifier: str) -> None:
        self._find(library_id).remove(identifier)

    def list(self, library_id: LibraryId) -> tuple[str, ...]:
        return self._find(library_id).list()

    def available_libraries(self) -> tuple[LibraryId, ...]:
        return tuple(library.library_id for library in self._libraries)

    def _find(self, library_id: LibraryId) -> ILibraryProvider:
        for library in self._libraries:
            if library.library_id == library_id:
                return library
        raise ScoreResolutionError(f"No library registered for id '{library_id.value}'")
