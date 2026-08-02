import pytest

import src.osap.cli.main as cli_main
from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.work_resolution_engine import WorkResolutionEngine
from src.osap.application.work_resolver import WorkResolver
from src.osap.bootstrap.container import Container
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.score_ranking import ScoreRanking
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    Duration,
    ProviderId,
    SourceId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.catalog_provider import ICatalogProvider
from src.osap.ports.ranking_engine import IRankingEngine


class FakeCatalog(ICatalogProvider):
    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("imslp")

    def required_resources(self) -> tuple[str, ...]:
        return ()

    def search(self, request: ResolveRequest) -> tuple[CandidateRepresentation, ...]:
        return (
            CandidateRepresentation(
                candidate_id=CandidateId("c1"),
                work_descriptor=WorkDescriptor(work_id=WorkId("w1"), title="Canço de Comiat"),
                provider_id=self.provider_id,
                format=OutputFormat.MUSICXML,
                confidence=Confidence(0.9),
            ),
        )

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        return self.search(request)[0]

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            catalog_id=CatalogId("imslp"),
            name="IMSLP",
            provider_id=self.provider_id,
            source="x",
            status=CatalogStatus.AVAILABLE,
        )

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(provider_id=self.provider_id, formats=(OutputFormat.MUSICXML,))

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        return AcquisitionResult(
            provider_id=self.provider_id,
            source=MusicalSource(SourceId("s1"), b"%PDF", OutputFormat.MUSICXML),
            confidence=Confidence(1.0),
            processing_time=Duration(0.0),
            format=OutputFormat.MUSICXML,
        )


class FakeRanking(IRankingEngine):
    def rank(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        request: ResolveRequest,
        config: RankingConfig,
    ) -> tuple[CandidateRepresentation, ...]:
        return candidates

    def rank_detailed(
        self,
        candidates: tuple[CandidateRepresentation, ...],
        request: ResolveRequest,
        config: RankingConfig,
    ) -> tuple[ScoreRanking, ...]:
        return tuple(ScoreRanking(candidate=c, total=1.0, details={"score": 1.0}, reason="test") for c in candidates)


class CliContainer(Container):
    def __init__(self) -> None:
        super().__init__()
        manager = CatalogManager()
        manager.register(FakeCatalog())
        self._engine = WorkResolutionEngine(
            catalog_manager=manager,
            ranking_engine=FakeRanking(),
            work_resolver=WorkResolver(),
            config=RankingConfig(),
        )

    def work_resolution_engine(self) -> WorkResolutionEngine:
        return self._engine


def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "wire", lambda c, cfg: CliContainer())


class TestCliResolve:
    def test_resolve_prints_result(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        _patch(monkeypatch)
        code = cli_main.main(["resolve", "Canço de Comiat"])
        out = capsys.readouterr().out
        assert code == 0
        assert "Descargando" in out
        assert "Resolución terminada" in out
        assert "imslp" in out
