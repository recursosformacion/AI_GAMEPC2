from dataclasses import dataclass, field
from datetime import datetime

from .output_format import OutputFormat
from .quality_level import QualityLevel
from .value_objects import CandidateId, Confidence, ProviderId
from .work_descriptor import WorkDescriptor


@dataclass(frozen=True)
class CandidateRepresentation:
    """A concrete form of a WorkDescriptor found in a catalog provider."""

    candidate_id: CandidateId
    work_descriptor: WorkDescriptor
    provider_id: ProviderId
    format: OutputFormat = OutputFormat.PDF
    origin: str | None = None
    license: str | None = None
    quality: QualityLevel = QualityLevel.UNREADABLE
    confidence: Confidence = Confidence(0.0)
    download_url: str | None = None
    view_url: str | None = None
    local_path: str | None = None
    edition: str | None = None
    public_domain: bool | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    date_added: datetime | None = None
    downloadable: bool = True
    manual_download: bool = False
    remote_id: str | None = None
    rating: float | None = None
    notes: str | None = None
    completeness: float = 1.0
    metadata: dict[str, object] = field(default_factory=dict)
