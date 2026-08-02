from dataclasses import dataclass, field

from .value_objects import WorkId, WorkIdentifier


@dataclass(frozen=True)
class WorkDescriptor:
    """Pure musical identity of a work, independent of any physical format.

    Describes the work itself (title, composer, movement, genres, expected
    instrumentation, musicological info). It contains no reference to formats
    or files.

    ``title`` is the *display* title: the best available title as a human
    should see it. It is never the output of a normalizer. ``canonical_title``
    and ``canonical_key`` are internal-only values used exclusively for
    grouping and comparing works; they are never shown to the user.
    """

    work_id: WorkId
    title: str
    subtitle: str | None = None
    composer: str | None = None
    arranger: str | None = None
    lyricist: str | None = None
    opus: str | None = None
    catalogue_number: str | None = None
    movement: str | None = None
    movement_number: int | None = None
    creation_year: int | None = None
    language: str | None = None
    genres: tuple[str, ...] = field(default_factory=tuple)
    instrumentation: tuple[str, ...] = field(default_factory=tuple)
    voices: tuple[str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    identifiers: tuple[WorkIdentifier, ...] = field(default_factory=tuple)
    canonical_title: str | None = None
    canonical_key: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        """The title the user should see. Always equals ``title``."""
        return self.title

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("WorkDescriptor title cannot be empty")
