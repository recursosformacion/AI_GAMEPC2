from dataclasses import dataclass


@dataclass(frozen=True)
class RequestId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("RequestId cannot be empty")


@dataclass(frozen=True)
class DocumentId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("DocumentId cannot be empty")


@dataclass(frozen=True)
class SourceId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("SourceId cannot be empty")


@dataclass(frozen=True)
class ScoreId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ScoreId cannot be empty")


@dataclass(frozen=True)
class ProviderId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ProviderId cannot be empty")


@dataclass(frozen=True)
class WorkId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("WorkId cannot be empty")


@dataclass(frozen=True)
class CatalogId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("CatalogId cannot be empty")


@dataclass(frozen=True)
class ResourceId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ResourceId cannot be empty")


@dataclass(frozen=True)
class CandidateId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("CandidateId cannot be empty")


@dataclass(frozen=True)
class EditionId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("EditionId cannot be empty")


@dataclass(frozen=True)
class ArrangementId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ArrangementId cannot be empty")


@dataclass(frozen=True)
class JobId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("JobId cannot be empty")


@dataclass(frozen=True)
class WorkIdentifier:
    """A structured external identifier of a work (e.g. ISMN, ISWC, catalogue)."""

    kind: str
    value: str

    def __post_init__(self) -> None:
        if not self.kind or not self.value:
            raise ValueError("WorkIdentifier requires both kind and value")


@dataclass(frozen=True)
class StrategyId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("StrategyId cannot be empty")


@dataclass(frozen=True)
class LibraryId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("LibraryId cannot be empty")


@dataclass(frozen=True)
class Confidence:
    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class Duration:
    seconds: float

    def __post_init__(self) -> None:
        if self.seconds < 0:
            raise ValueError("Duration cannot be negative")


@dataclass(frozen=True)
class DiagnosticMessage:
    text: str

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("DiagnosticMessage cannot be empty")
