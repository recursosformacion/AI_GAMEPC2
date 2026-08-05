import importlib
from collections.abc import Callable, Iterator
from typing import Protocol, cast

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.errors import ResourceUnavailableError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    ProviderId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.catalog_provider import ICatalogProvider

Row = dict[str, object]


class _DatasetEngine(Protocol):
    def filter(self, function: Callable[[Row], bool], num_proc: int | None = None) -> "_DatasetEngine": ...

    def to_iterable_dataset(self) -> "_IterableDataset": ...

    def __len__(self) -> int: ...


class _IterableDataset(Protocol):
    def __iter__(self) -> Iterator[Row]: ...


class _DatasetsModule(Protocol):
    def load_dataset(self, path: str, *, streaming: bool = False) -> _DatasetEngine: ...


class HuggingFaceCatalogProvider(ICatalogProvider):
    """A catalog backed by a Hugging Face dataset.

    The `datasets` library is the ONLY external dependency here, confined to
    this module and imported lazily. It never manages installation: the
    ResourceManager ensures the backing resource first.
    """

    def __init__(self, provider_id: str, dataset_path: str) -> None:
        self._provider_id = ProviderId(provider_id)
        self._path = dataset_path

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            offline=True,
            supports_streaming=True,
            formats=(OutputFormat.MUSICXML,),
            public_domain_only=True,
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId(self._provider_id.value),
            name=self._provider_id.value,
            provider_id=self.provider_id,
            source=self._path,
            status=CatalogStatus.INSTALLED,
        )

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        try:
            module = self._engine()
            dataset = module.load_dataset(self._path, streaming=request.offline)
            predicate = _to_predicate(request)
            rows = dataset.filter(predicate).to_iterable_dataset()
            return tuple(_to_candidate(row, self._provider_id) for row in rows)
        except ResourceUnavailableError:
            raise
        except Exception:
            # The dataset cannot be served right now (e.g. not available locally
            # or unreachable). The user only ever sees "unavailable".
            raise ResourceUnavailableError("source unavailable") from None

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        candidates = self.search(SearchRequest.from_resolve(request))
        return candidates[0] if candidates else None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        raise NotImplementedError("HuggingFace catalog download is not implemented yet")

    @staticmethod
    def _engine() -> _DatasetsModule:
        try:
            return cast("_DatasetsModule", importlib.import_module("datasets"))
        except ImportError as exc:
            raise RuntimeError("The 'datasets' library is required for Hugging Face catalogs") from exc


def _to_predicate(request: SearchRequest) -> Callable[[Row], bool]:
    def predicate(row: Row) -> bool:
        if request.title and request.title.lower() not in str(row.get("title") or "").lower():
            return False
        if request.composer and request.composer.lower() not in str(row.get("composer") or "").lower():
            return False
        if request.genre and request.genre.lower() not in str(row.get("genre") or "").lower():
            return False
        return not (request.language and request.language.lower() not in str(row.get("language") or "").lower())

    return predicate


def _to_candidate(row: Row, provider_id: ProviderId) -> CandidateRepresentation:
    title = str(row.get("title") or "Untitled")
    row_id = str(row.get("id") or abs(hash(title)))
    descriptor = WorkDescriptor(
        work_id=WorkId(f"{provider_id.value}-{row_id}"),
        title=title,
        composer=_opt(row, "composer"),
        language=_opt(row, "language"),
    )
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{provider_id.value}-{row_id}"),
        work_descriptor=descriptor,
        provider_id=provider_id,
        format=OutputFormat.MUSICXML,
        confidence=Confidence(0.5),
        license=_opt(row, "license"),
        quality=QualityLevel.UNREADABLE,
        metadata={"row_id": row_id},
    )


def _opt(row: Row, key: str) -> str | None:
    value = row.get(key)
    return None if value is None else str(value)
