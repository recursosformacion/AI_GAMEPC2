from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import CatalogId, ProviderId
from src.osap.ports.catalog_provider import ICatalogProvider


class FilesystemCatalogProvider(ICatalogProvider):
    def __init__(self, name: str = "filesystem") -> None:
        self._provider_id = ProviderId(name)

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            offline=True,
            formats=(OutputFormat.MUSICXML, OutputFormat.PDF),
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId(self._provider_id.value),
            name=self._provider_id.value,
            provider_id=self.provider_id,
            source="filesystem",
            status=CatalogStatus.INSTALLED,
        )

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        raise NotImplementedError

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        raise NotImplementedError

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        raise NotImplementedError
