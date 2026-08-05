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


class CPDLCatalogProvider(ICatalogProvider):
    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("cpdl")

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self.provider_id,
            offline=True,
            formats=(OutputFormat.MUSICXML, OutputFormat.PDF),
            public_domain_only=True,
        )

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("cpdl"),
            name="CPDL",
            provider_id=self.provider_id,
            source="https://www.cpdl.org",
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
