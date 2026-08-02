from src.osap.application.capabilities_dto import CapabilitiesDto
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import ProviderId


class TestCapabilitiesDto:
    def test_build(self) -> None:
        caps = CatalogCapabilities(
            provider_id=ProviderId("openscore"),
            supports_download=True,
            formats=(OutputFormat.MUSICXML,),
        )
        dto = CapabilitiesDto.build("openscore", caps, available=True, authenticated=False)
        assert dto["provider"] == "openscore"
        assert dto["available"] is True
        assert dto["supports_musicxml"] is True
        assert dto["supports_pdf"] is False
        assert dto["priority"] == 85

    def test_imslp_pdf(self) -> None:
        caps = CatalogCapabilities(provider_id=ProviderId("imslp"), formats=(OutputFormat.PDF,))
        dto = CapabilitiesDto.build("imslp", caps, available=True, authenticated=False)
        assert dto["supports_pdf"] is True
        assert dto["supports_musicxml"] is False
