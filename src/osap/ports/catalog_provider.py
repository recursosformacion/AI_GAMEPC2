from abc import ABC, abstractmethod

from ..domain.acquisition_result import AcquisitionResult
from ..domain.candidate_representation import CandidateRepresentation
from ..domain.catalog_capabilities import CatalogCapabilities
from ..domain.catalog_info import CatalogInfo
from ..domain.output_format import OutputFormat
from ..domain.resolve_request import ResolveRequest
from ..domain.value_objects import ProviderId


class ICatalogProvider(ABC):
    """Any source able to offer musical works (catalog).

    A catalog may be backed by a Hugging Face dataset, GitHub, a REST API, a
    local database, XML/JSON, MediaWiki, a filesystem, etc. The domain never
    knows which. Each provider decides internally how to implement the
    operations.
    """

    @property
    @abstractmethod
    def provider_id(self) -> ProviderId:
        raise NotImplementedError

    @abstractmethod
    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        raise NotImplementedError

    @abstractmethod
    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> CatalogInfo:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> CatalogCapabilities:
        raise NotImplementedError
