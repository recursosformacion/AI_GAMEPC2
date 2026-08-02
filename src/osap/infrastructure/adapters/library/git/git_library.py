from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.value_objects import LibraryId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.library_provider import ILibraryProvider


class GitLibrary(ILibraryProvider):
    @property
    def library_id(self) -> LibraryId:
        return LibraryId("git")

    def save(self, source: MusicalSource, identifier: str) -> None:
        raise NotImplementedError

    def store_work(
        self, work: WorkDescriptor, source: MusicalSource, metadata: dict[str, object], identifier: str
    ) -> None:
        raise NotImplementedError

    def exists(self, identifier: str) -> bool:
        raise NotImplementedError

    def update(self, source: MusicalSource, identifier: str) -> None:
        raise NotImplementedError

    def remove(self, identifier: str) -> None:
        raise NotImplementedError

    def list(self) -> tuple[str, ...]:
        raise NotImplementedError
