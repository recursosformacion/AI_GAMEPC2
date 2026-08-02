import pytest

from src.osap.application.catalog_manager import CatalogManager
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import CatalogId, ProviderId
from src.osap.ports.catalog_provider import ICatalogProvider


class FakeCatalog(ICatalogProvider):
    def __init__(self, provider_id: str) -> None:
        self._provider_id = ProviderId(provider_id)
        self.searches = 0

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def required_resources(self) -> tuple[str, ...]:
        return ()

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        self.searches += 1
        return ()

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        return None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        raise NotImplementedError

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId(self._provider_id.value),
            name=self._provider_id.value,
            provider_id=self._provider_id,
            source="x",
            status=CatalogStatus.INSTALLED,
        )

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            provider_id=self._provider_id,
            formats=(OutputFormat.MUSICXML,),
            offline=True,
        )


class TestCatalogManager:
    def test_register_and_list(self) -> None:
        manager = CatalogManager()
        manager.register(FakeCatalog("pdmx"))
        manager.register(FakeCatalog("imslp"))
        assert manager.list() == (CatalogId("pdmx"), CatalogId("imslp"))
        assert manager.available(CatalogId("pdmx")) is True

    def test_capabilities_and_info(self) -> None:
        manager = CatalogManager()
        manager.register(FakeCatalog("imslp"))
        assert manager.capabilities(CatalogId("imslp")).offline is True
        assert manager.info(CatalogId("imslp")).name == "imslp"

    def test_unknown_raises(self) -> None:
        with pytest.raises(ScoreResolutionError):
            CatalogManager().info(CatalogId("nope"))
