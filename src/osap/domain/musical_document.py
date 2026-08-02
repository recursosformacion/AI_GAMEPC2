from dataclasses import dataclass, field
from pathlib import Path

from .document_type import DocumentType
from .value_objects import DocumentId


@dataclass(frozen=True)
class MusicalDocument:
    document_id: DocumentId
    document_type: DocumentType
    path: Path
    metadata: dict[str, object] = field(default_factory=dict)
