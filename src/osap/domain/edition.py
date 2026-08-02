from dataclasses import dataclass, field

from .value_objects import EditionId, WorkIdentifier
from .work_descriptor import WorkDescriptor


@dataclass(frozen=True)
class Edition:
    """A concrete published edition of a MusicalWork."""

    edition_id: EditionId
    work: WorkDescriptor
    publisher: str | None = None
    year: int | None = None
    editor: str | None = None
    language: str | None = None
    identifiers: tuple[WorkIdentifier, ...] = field(default_factory=tuple)
    metadata: dict[str, object] = field(default_factory=dict)
