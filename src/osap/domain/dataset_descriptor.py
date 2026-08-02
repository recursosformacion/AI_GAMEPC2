from dataclasses import dataclass, field
from datetime import datetime

from .dataset_status import DatasetStatus
from .output_format import OutputFormat
from .value_objects import DatasetId


@dataclass(frozen=True)
class DatasetVersion:
    version: str
    released: datetime | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("DatasetVersion requires a version string")


@dataclass(frozen=True)
class DatasetDescriptor:
    """Declarative description of a dataset available to install.

    A dataset is an optional local resource. Its absence is not an error: it is
    treated like an external drive that is not connected yet. The domain never
    knows Hugging Face; it only knows the declarative descriptor.
    """

    dataset_id: DatasetId
    name: str
    hf_path: str
    description: str | None = None
    expected_size_bytes: int | None = None
    license: str | None = None
    formats: tuple[OutputFormat, ...] = field(default_factory=tuple)
    official_url: str | None = None
    status: DatasetStatus = DatasetStatus.NOT_PRESENT
    versions: tuple[DatasetVersion, ...] = field(default_factory=tuple)
