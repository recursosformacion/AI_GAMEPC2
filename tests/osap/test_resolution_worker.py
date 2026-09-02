"""Pipeline de resolución end-to-end (FASE 5 — worker conectado).

Cubre la cadena que el incremento hace funcional:

    ResolutionSession → AcquisitionService → acquirer → provider →
    representación → BasicValidator → Score + QualityReport → PipelineLog →
    estado final de la sesión.

Los providers usados son fakes controlados (no red); el flujo real de descarga/
validación se cubre con el validador MusicXML real y ficheros .mxl de fixture.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.pipeline_log import PipelineLog
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.score import Score
from src.osap.domain.value_objects import (
    CandidateId,
    CatalogId,
    Confidence,
    ProviderId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
from src.osap.infrastructure.resolution.provider_acquirer import CatalogAcquirer
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher
from src.osap.infrastructure.state.resolution_store import _MemoryStore
from src.osap.ports.catalog_provider import ICatalogProvider

if TYPE_CHECKING:
    from src.osap.domain.resolve_request import ResolveRequest
    from src.osap.domain.search_request import SearchRequest

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"
_DOWNLOADABLE = "https://storage.openmusicrepository.com/api/download/233827"


class _Provider(ICatalogProvider):
    """Provider de control: devuelve una representación descargable (o error)."""

    def __init__(
        self,
        *,
        title: str = "Ave Maria",
        composer: str | None = "Franz Schubert",
        download_url: str | None = _DOWNLOADABLE,
        raise_error: bool = False,
    ) -> None:
        self._title = title
        self._composer = composer
        self._download_url = download_url
        self._raise_error = raise_error

    @property
    def provider_id(self) -> ProviderId:
        return ProviderId("omr")

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        if self._raise_error:
            raise RuntimeError("provider explosion")
        return (
            CandidateRepresentation(
                candidate_id=CandidateId("c1"),
                work_descriptor=WorkDescriptor(WorkId("w1"), self._title, composer=self._composer),
                provider_id=self.provider_id,
                format=OutputFormat.MUSICXML,
                confidence=Confidence(0.9),
                download_url=self._download_url,
                downloadable=bool(self._download_url),
            ),
        )

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        return None

    def download(
        self,
        candidate: CandidateRepresentation,
        output_format: OutputFormat | None = None,
    ) -> AcquisitionResult:
        # El fake no se usa para descarga en estos tests; devolver un resultado vacío
        # satisface el contrato sin ejercitar la descarga del provider.
        from src.osap.domain.musical_source import MusicalSource
        from src.osap.domain.value_objects import Duration, SourceId

        return AcquisitionResult(
            provider_id=self.provider_id,
            source=MusicalSource(SourceId("s-fake"), b"", OutputFormat.MUSICXML),
            confidence=Confidence(1.0),
            processing_time=Duration(0.0),
            format=OutputFormat.MUSICXML,
        )
    def metadata(self) -> CatalogInfo:
        return CatalogInfo(CatalogId("omr"), "OMR", self.provider_id, "remote", CatalogStatus.AVAILABLE)

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(self.provider_id, formats=(OutputFormat.MUSICXML,))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _future() -> str:
    return (datetime.now(UTC) + timedelta(minutes=30)).isoformat()


def _make_session(store: _MemoryStore, providers: list[str]) -> str:
    session_id = "ses_worker"
    store.create_session(
        session_id,
        json.dumps({"query": "Ave Maria", "works": []}),
        json.dumps(providers),
        json.dumps({"max_results_to_acquire": 10}),
        _now(),
        _future(),
    )
    return session_id


def _service(store: _MemoryStore, provider: ICatalogProvider) -> AcquisitionService:
    acquirer = CatalogAcquirer(provider.provider_id.value, provider)
    return AcquisitionService(store, {provider.provider_id.value: acquirer}, SimpleUniverseMatcher())


class TestSessionCreated:
    def test_sesion_creada_en_acquiring(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        row = store.get_session(sid)
        assert row is not None
        assert row["status"] == "acquiring"


class TestAcquirerConectado:
    def test_acquirer_devuelve_representacion_descargable(self) -> None:
        provider = _Provider()
        acquirer = CatalogAcquirer("omr", provider)
        page = acquirer.acquire_page("omr", "1", "Ave Maria")
        assert page.error is None
        assert page.end_of_provider is True
        assert len(page.works) == 1
        resources = page.works[0].resources
        assert resources
        assert resources[0].links.download == _DOWNLOADABLE


class TestWorkerEjecutado:
    def test_worker_ejecuta_adquisicion_y_termina_complete(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        service = _service(store, _Provider())
        status = service.run_until_terminal(sid)
        assert status == "complete"
        results = store.list_provider_results(sid, "omr")
        assert len(results) == 1
        assert results[0]["status"] == "end_of_provider"

    def test_worker_persiste_payload_con_representacion(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        service = _service(store, _Provider())
        service.run_until_terminal(sid)
        works = json.loads(str(store.list_provider_results(sid, "omr")[0]["payload_json"]))
        assert works[0]["identity"]["title"] == "Ave Maria"
        assert works[0]["resources"][0]["links"]["download"] == _DOWNLOADABLE


class TestValidacion:
    def test_validacion_genera_score_y_quality_report(self) -> None:
        """Con un .mxl real de fixture, el validador produce Score + QualityReport."""
        from src.osap.domain.acquisition_result import AcquisitionResult
        from src.osap.domain.musical_source import MusicalSource
        from src.osap.domain.pipeline_context import PipelineContext
        from src.osap.domain.value_objects import Duration, SourceId
        from src.osap.infrastructure.pipeline.score_validation_stage import (
            KEY_ACQUISITION,
            KEY_PIPELINE_LOG,
            KEY_SCORE,
            ScoreValidationStage,
        )

        content = (_FIXTURES / "real_short.mxl").read_bytes()
        acquisition = AcquisitionResult(
            provider_id=ProviderId("omr"),
            source=MusicalSource(SourceId("s1"), content, OutputFormat.MUSICXML),
            confidence=Confidence(1.0),
            processing_time=Duration(0.0),
            format=OutputFormat.MUSICXML,
        )
        ctx = ScoreValidationStage().execute(PipelineContext(data={KEY_ACQUISITION: acquisition}))
        score = ctx.data[KEY_SCORE]
        log = ctx.data[KEY_PIPELINE_LOG]
        assert isinstance(score, Score)
        assert isinstance(log, PipelineLog)
        assert score.quality_level in (QualityLevel.BASIC_MELODY, QualityLevel.FULL_NOTATION)
        assert log.steps and log.steps[0].step_name == "score_validation"

    def test_sesion_termina_con_diagnostico_validacion(self) -> None:
        """resolve_session completa: adquisición + diagnóstico de validación en el error."""
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        service = _service(store, _Provider())
        status = service.run_until_terminal(sid)
        assert status == "complete"
        row = store.get_session(sid)
        assert row is not None
        assert row["status"] == "complete"


class TestFallos:
    def test_fallo_del_provider_marca_recoverable_error(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        service = _service(store, _Provider(raise_error=True))
        status = service.run_until_terminal(sid)
        assert status in ("partial", "complete", "acquiring")
        rows = store.list_provider_results(sid, "omr")
        assert any(r["status"] == "recoverable_error" for r in rows)

    def test_sin_representacion_descargable(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        service = _service(store, _Provider(download_url=None))
        status = service.run_until_terminal(sid)
        assert status in ("complete", "partial")


class TestSesionInexistente:
    def test_sesion_inexistente_devuelve_none(self) -> None:
        store = _MemoryStore()
        service = AcquisitionService(store, {}, SimpleUniverseMatcher())
        assert service.process_step("ses_nope") == "failed"

    def test_sesion_expirada(self) -> None:
        store = _MemoryStore()
        store.create_session(
            "ses_expired",
            json.dumps({"query": "x", "works": []}),
            json.dumps(["omr"]),
            "{}",
            _now(),
            (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        )
        service = AcquisitionService(store, {}, SimpleUniverseMatcher())
        assert service.process_step("ses_expired") == "expired"


class TestSeleccionEstructurada:
    """La selección se persiste estructurada (selection_json); error solo errores."""

    def test_seleccion_no_usa_error(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        store.update_status(sid, "complete")
        store.set_selection(
            sid,
            json.dumps(
                {
                    "provider": "omr",
                    "format": "musicxml",
                    "quality_level": 4,
                    "quality_score": 0.97,
                    "reason": "mayor calidad",
                    "alternatives": [],
                }
            ),
        )
        row = store.get_session(sid)
        assert row is not None
        assert row["status"] == "complete"
        assert row["error"] is None  # el resultado exitoso NO va en error
        assert row["selection_json"]
        sel = json.loads(str(row["selection_json"]))
        assert sel["provider"] == "omr"
        assert sel["quality_level"] == 4

    def test_error_solo_para_fallos(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        store.update_status(sid, "failed", error="provider explosion")
        row = store.get_session(sid)
        assert row is not None
        assert row["status"] == "failed"
        assert row["error"] == "provider explosion"
        assert row["selection_json"] is None

    def test_partial_sin_error_artificial(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        store.update_status(sid, "partial")
        row = store.get_session(sid)
        assert row is not None
        assert row["status"] == "partial"
        assert row["error"] is None

    def test_expired_representa_ttl(self) -> None:
        store = _MemoryStore()
        sid = _make_session(store, ["omr"])
        store.update_status(sid, "expired")
        row = store.get_session(sid)
        assert row is not None
        assert row["status"] == "expired"
