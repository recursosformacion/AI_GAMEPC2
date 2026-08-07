from dataclasses import FrozenInstanceError

import pytest

from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.errors import DomainError, ResourceUnavailableError, ScoreResolutionError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.resolve_result import ResolveResult
from src.osap.domain.resource import Resource, ResourceKind, ResourceStatus
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    DiagnosticMessage,
    Duration,
    ProviderId,
    ResourceId,
    WorkId,
    WorkIdentifier,
)
from src.osap.domain.work_descriptor import WorkDescriptor


class TestValueObjects:
    def test_ids(self) -> None:
        assert WorkId("w1").value == "w1"
        assert CatalogId("c1").value == "c1"
        assert ResourceId("r1").value == "r1"
        assert CandidateId("k1").value == "k1"
        assert ProviderId("p1").value == "p1"

    def test_work_identifier(self) -> None:
        identifier = WorkIdentifier("iswc", "T-010.000.000-1")
        assert identifier.kind == "iswc"
        with pytest.raises(ValueError):
            WorkIdentifier("", "x")

    def test_confidence(self) -> None:
        assert Confidence(0.9).value == 0.9
        with pytest.raises(ValueError):
            Confidence(1.5)

    def test_duration_and_message(self) -> None:
        assert Duration(1.0).seconds == 1.0
        assert DiagnosticMessage("x").text == "x"
        with pytest.raises(ValueError):
            DiagnosticMessage("")


class TestWorkDescriptor:
    def test_create(self) -> None:
        work = WorkDescriptor(
            work_id=WorkId("w1"),
            title="Cançó de Comiat",
            composer="Eduard Toldrà",
            voices=("S", "A", "T", "B"),
            identifiers=(WorkIdentifier("iswc", "T-1"),),
        )
        assert work.title == "Cançó de Comiat"
        assert work.composer == "Eduard Toldrà"

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValueError):
            WorkDescriptor(work_id=WorkId("w1"), title="")

    def test_is_frozen(self) -> None:
        work = WorkDescriptor(work_id=WorkId("w1"), title="Obra")
        with pytest.raises(FrozenInstanceError):
            work.title = "Otra"  # type: ignore[misc]


class TestCandidateRepresentation:
    def test_create(self) -> None:
        work = WorkDescriptor(work_id=WorkId("w1"), title="Ave Maria")
        candidate = CandidateRepresentation(
            candidate_id=CandidateId("c1"),
            work_descriptor=work,
            provider_id=ProviderId("imslp"),
            format=OutputFormat.MUSICXML,
            local_path="/tmp/score.mxl",
            size_bytes=1024,
            checksum="abc",
        )
        assert candidate.work_descriptor == work
        assert candidate.local_path == "/tmp/score.mxl"
        assert candidate.size_bytes == 1024


class TestResolveRequest:
    def test_defaults(self) -> None:
        request = ResolveRequest(title="Cançó de Comiat")
        assert request.online is True
        assert request.offline is True
        assert request.desired_format is None

    def test_is_frozen(self) -> None:
        request = ResolveRequest(title="X")
        with pytest.raises(FrozenInstanceError):
            request.title = "Y"  # type: ignore[misc]


class TestResolveResult:
    def test_create(self) -> None:
        result = ResolveResult(
            request=ResolveRequest(title="Ave Maria"),
            selected_work=WorkDescriptor(work_id=WorkId("w1"), title="Ave Maria"),
            chosen=None,
            ranking=(),
            providers_used=(),
            duration=Duration(0.5),
            selection_reason="no candidate",
        )
        assert result.chosen is None
        assert result.duration == Duration(0.5)


class TestResource:
    def test_create(self) -> None:
        resource = Resource(
            resource_id=ResourceId("omr"),
            name="OMR",
            kind=ResourceKind.CATALOG,
            provider=ProviderId("omr"),
            status=ResourceStatus.NOT_INSTALLED,
            size=100,
        )
        assert resource.kind == ResourceKind.CATALOG
        assert resource.status == ResourceStatus.NOT_INSTALLED

    def test_kind_and_status_enums(self) -> None:
        assert ResourceKind.CATALOG.value == "catalog"
        assert ResourceKind.MODEL.value == "model"
        assert ResourceStatus.INDEX_ONLY.value == "index_only"
        assert ResourceStatus.PARTIAL.value == "partial"


class TestCatalog:
    def test_capabilities(self) -> None:
        caps = CatalogCapabilities(provider_id=ProviderId("imslp"), offline=False)
        assert caps.offline is False
        assert caps.supports_search is True

    def test_info(self) -> None:
        info = CatalogInfo(
            catalog_id=CatalogId("imslp"),
            name="IMSLP",
            provider_id=ProviderId("imslp"),
            source="https://imslp.org",
            status=CatalogStatus.AVAILABLE,
        )
        assert info.status == CatalogStatus.AVAILABLE


class TestErrors:
    def test_hierarchy(self) -> None:
        assert issubclass(ResourceUnavailableError, DomainError)
        assert issubclass(ScoreResolutionError, DomainError)
