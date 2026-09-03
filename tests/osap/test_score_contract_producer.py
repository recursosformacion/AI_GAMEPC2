"""Tests del productor OSAP de `ScoreContract` (endpoint de sesión resuelta).

El circuito probado (con contenido `.mxl` real de fixture, sin red):
sesión resuelta → selección → descarga → validación (BasicValidator) → `Score` →
`score_to_contract` → JSON válido consumible por el contrato de Chorus hasta
`ExerciseGenerator`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import src.osap.api.platform as platform_module
from src.chorus.application.use_cases.generate_materials import GenerateMaterialsUseCase
from src.chorus.contract import ScoreContract, contract_to_score
from src.chorus.domain.material_type import MaterialType
from src.chorus.infrastructure.generators.exercise_generator import ExerciseGenerator

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"
REAL_MXL = (FIXTURES / "real_short.mxl").read_bytes()
URL_OMR = "https://storage.openmusicrepository.com/api/download/233827"


class _FakeResolutionStore:
    def __init__(
        self,
        session: Any | None,
        results: list[dict[str, Any]] | None = None,
    ) -> None:
        self._session = session
        self._results = results or []

    def get_session(self, session_id: str) -> dict[str, object] | None:  # noqa: ARG002
        return self._session

    def list_all_provider_results(self, session_id: str) -> list[dict[str, object]]:  # noqa: ARG002
        return self._results


def _result(identity: dict[str, Any], url: str) -> dict[str, Any]:
    payload = [
        {
            "provider": "omr",
            "identity": identity,
            "resources": [{"format": "musicxml", "links": {"download": url}}],
        }
    ]
    return {"provider": "omr", "payload_json": json.dumps(payload)}


def _selection_json(url: str) -> str:
    return json.dumps(
        {
            "provider": "omr",
            "format": "musicxml",
            "url": url,
            "quality_level": 2,
            "quality_score": 0.7,
            "reason": "mayor calidad",
            "alternatives": [],
            "warnings": [],
        }
    )


def _producer(session: dict[str, Any] | None, results: list[dict[str, Any]], monkeypatch: Any) -> Any:
    api: Any = platform_module.PlatformApi.__new__(platform_module.PlatformApi)
    api._resolution_store = _FakeResolutionStore(session, results)
    monkeypatch.setattr(platform_module, "_fetch_url_bytes", lambda url: REAL_MXL if url == URL_OMR else None)
    return api


class TestScoreContractProducer:
    def test_produce_contrato_consumible_por_chorus(self, monkeypatch: Any) -> None:
        session = {"status": "complete", "selection_json": _selection_json(URL_OMR)}
        results = [_result({"title": "Ave Maria", "composer": None}, URL_OMR)]
        api = _producer(session, results, monkeypatch)

        code, err_code, message, payload = api.score_contract_for_session("ses_1")
        assert code == 200, message
        assert err_code == ""
        assert payload is not None
        contract = payload["score_contract"]
        assert isinstance(contract, dict)
        assert contract["schema_version"] == 1
        assert contract["title"] == "Ave Maria"
        structure = contract["structure"]
        assert structure["parts"] == 1
        assert structure["measures"] == 14
        assert structure["notes"] == 100
        assert payload["work"]["provider"] == "omr"

        # Compatibilidad: OSAP JSON → contrato Chorus → Score → material real.
        parsed = ScoreContract.from_dict(contract)
        score = contract_to_score(parsed)
        use_case = GenerateMaterialsUseCase((ExerciseGenerator(),))
        material = use_case.generate(score, MaterialType.EXERCISE)
        assert material.material_type == MaterialType.EXERCISE
        assert material.metadata["parts"] == 1
        assert material.metadata["measures"] == 14
        assert material.metadata["notes"] == 100
        assert material.metadata["title"] == "Ave Maria"

    def test_sesion_inexistente_404(self, monkeypatch: Any) -> None:
        api = _producer(None, [], monkeypatch)
        code, err_code, _msg, payload = api.score_contract_for_session("ses_no")
        assert code == 404
        assert err_code == "SESSION_NOT_FOUND"
        assert payload is None

    def test_sin_seleccion_409(self, monkeypatch: Any) -> None:
        session = {"status": "complete", "selection_json": ""}
        api = _producer(session, [], monkeypatch)
        code, err_code, _msg, payload = api.score_contract_for_session("ses_1")
        assert code == 409
        assert err_code == "NO_SELECTION"
        assert payload is None

    def test_descarga_fallida_502(self, monkeypatch: Any) -> None:
        session = {"status": "complete", "selection_json": _selection_json("https://x/otra")}
        api = _producer(session, [], monkeypatch)
        code, err_code, _msg, payload = api.score_contract_for_session("ses_1")
        assert code == 502
        assert err_code == "FETCH_FAILED"
        assert payload is None

    def test_representacion_invalida_422(self, monkeypatch: Any) -> None:
        session = {"status": "complete", "selection_json": _selection_json(URL_OMR)}
        results = [_result({"title": "Basura", "composer": None}, URL_OMR)]
        api: Any = platform_module.PlatformApi.__new__(platform_module.PlatformApi)
        api._resolution_store = _FakeResolutionStore(session, results)
        monkeypatch.setattr(platform_module, "_fetch_url_bytes", lambda url: b"no es un musicxml")
        code, err_code, _msg, payload = api.score_contract_for_session("ses_1")
        assert code == 422
        assert err_code == "INVALID_REPRESENTATION"
        assert payload is None

    def test_error_interno_500_controlado(self, monkeypatch: Any) -> None:
        session = {"status": "complete", "selection_json": _selection_json(URL_OMR)}
        results = [_result({"title": "A", "composer": None}, URL_OMR)]
        api: Any = platform_module.PlatformApi.__new__(platform_module.PlatformApi)
        api._resolution_store = _FakeResolutionStore(session, results)
        monkeypatch.setattr(platform_module, "_fetch_url_bytes", lambda url: REAL_MXL)

        def boom(content: bytes, identity: dict[str, object] | None) -> dict[str, object]:
            raise RuntimeError("detalle interno")

        monkeypatch.setattr(platform_module, "_validate_to_contract", boom)
        code, err_code, message, payload = api.score_contract_for_session("ses_1")
        assert code == 500
        assert err_code == "INTERNAL"
        assert "detalle interno" not in message
        assert payload is None

    def test_identidad_semantica_correcta(self, monkeypatch: Any) -> None:
        """La obra del contrato es la dueña de la URL seleccionada, no otra."""
        url_a = "https://storage.openmusicrepository.com/api/download/1"
        url_b = "https://storage.openmusicrepository.com/api/download/2"
        session = {"status": "complete", "selection_json": _selection_json(url_b)}
        results = [
            _result({"title": "Otra Obra", "composer": "Otro"}, url_a),
            _result({"title": "Ave Maria", "composer": "Mozart"}, url_b),
        ]
        api: Any = platform_module.PlatformApi.__new__(platform_module.PlatformApi)
        api._resolution_store = _FakeResolutionStore(session, results)
        monkeypatch.setattr(
            platform_module,
            "_fetch_url_bytes",
            lambda url: REAL_MXL if url == url_b else None,
        )
        code, _err, _msg, payload = api.score_contract_for_session("ses_1")
        assert code == 200
        work = payload["work"]
        assert work["title"] == "Ave Maria"
        assert work["composer"] == "Mozart"


class TestEndpointHTTP:
    def test_endpoint_devuelve_contrato(self, monkeypatch: Any) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake_produce(
            self: Any, session_id: str
        ) -> tuple[int, str, str, dict[str, object] | None]:
            if session_id == "ses_no":
                return 404, "SESSION_NOT_FOUND", "Sesión no encontrada", None
            contract = {
                "schema_version": 1,
                "title": "Ave Maria",
                "composer": None,
                "structure": {"parts": 1, "measures": 14, "notes": 100, "voices": 1, "has_lyrics": False},
                "quality": {"level": 2, "report": {"structure": 1.0}},
                "diagnostics": {"errors": [], "warnings": []},
            }
            return 200, "", "", {"score_contract": contract, "work": {"title": "Ave Maria"}}

        monkeypatch.setattr(PlatformApi, "score_contract_for_session", fake_produce)
        with TestClient(platform_app.create_platform_app()) as client:
            ok_resp = client.get("/api/v1/sessions/ses_1/score-contract")
            assert ok_resp.status_code == 200
            body = ok_resp.json()
            assert body["success"] is True
            assert body["data"]["score_contract"]["schema_version"] == 1
            assert body["data"]["work"]["title"] == "Ave Maria"
            missing = client.get("/api/v1/sessions/ses_no/score-contract")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"
