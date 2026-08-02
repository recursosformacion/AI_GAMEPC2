from abc import ABC, abstractmethod

from ..domain.musical_source import MusicalSource
from ..domain.value_objects import LibraryId
from ..domain.work_descriptor import WorkDescriptor


class ILibraryProvider(ABC):
    """Stores resolved works in a user-selected library, preserving provenance."""

    @property
    @abstractmethod
    def library_id(self) -> LibraryId:
        raise NotImplementedError

    @abstractmethod
    def save(self, source: MusicalSource, identifier: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def store_work(
        self, work: WorkDescriptor, source: MusicalSource, metadata: dict[str, object], identifier: str
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, identifier: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def update(self, source: MusicalSource, identifier: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove(self, identifier: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> tuple[str, ...]:
        raise NotImplementedError
