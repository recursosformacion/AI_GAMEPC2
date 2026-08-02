from dataclasses import dataclass, field

from .musical_document import MusicalDocument
from .output_format import OutputFormat
from .preference_policy import SourcePreferencePolicy
from .request_type import RequestType
from .value_objects import LibraryId, RequestId


@dataclass(frozen=True)
class MusicalRequest:
    request_id: RequestId
    request_type: RequestType
    query: str | None = None
    composer: str | None = None
    document: MusicalDocument | None = None
    preferred_output: OutputFormat = OutputFormat.SCORE
    preferred_library: LibraryId | None = None
    preference_policy: SourcePreferencePolicy | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        text_types = (RequestType.TITLE, RequestType.COMPOSER, RequestType.PARTIAL_TITLE)
        if self.request_type in text_types and not self.query:
            raise ValueError("A text-based request requires a non-empty query")

        document_types = (
            RequestType.DOCUMENT,
            RequestType.IMAGE,
            RequestType.MUSICXML,
            RequestType.MEI,
            RequestType.MIDI,
        )
        if self.request_type in document_types and self.document is None:
            raise ValueError("A document-based request requires a document")
