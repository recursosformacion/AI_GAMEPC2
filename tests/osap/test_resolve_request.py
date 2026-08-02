from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.resolve_request import ResolveRequest, ResolveRequestBuilder
from src.osap.domain.value_objects import ProviderId


class TestResolveRequestBuilder:
    def test_builds_rich_request(self) -> None:
        request = (
            ResolveRequestBuilder()
            .text("Mozart Nocturnes")
            .composer("Wolfgang Amadeus Mozart")
            .genre("serenade")
            .language("de")
            .voices("SATB")
            .format(OutputFormat.MUSICXML)
            .public_domain(True)
            .build()
        )
        assert isinstance(request, ResolveRequest)
        assert request.query == "Mozart Nocturnes"
        assert request.composer == "Wolfgang Amadeus Mozart"
        assert request.voices == ("SATB",)
        assert request.desired_format == OutputFormat.MUSICXML
        assert request.public_domain is True

    def test_immutable(self) -> None:
        first = ResolveRequestBuilder().title("A")
        second = first.title("B")
        assert first.build().title == "A"
        assert second.build().title == "B"

    def test_provider_constraints(self) -> None:
        request = (
            ResolveRequestBuilder().allow_provider(ProviderId("imslp")).exclude_provider(ProviderId("pdmx")).build()
        )
        assert request.allowed_providers == (ProviderId("imslp"),)
        assert request.excluded_providers == (ProviderId("pdmx"),)

    def test_quality_min(self) -> None:
        request = ResolveRequestBuilder().min_quality(QualityLevel.FULL_NOTATION).build()
        assert request.min_quality == QualityLevel.FULL_NOTATION
