"""Tests del vertical slice web de Chorus sobre la nueva frontera (contrato Score).

POST /generate recibe el `ScoreContract` serializado (JSON) y POST /generate-file
mantiene la entrada provisional .mxl para la demo. Los tests usan el `.mxl` real de
los fixtures y el `GenerateMaterialsUseCase` real (sin mocks en el camino).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.chorus.application.use_cases.generate_materials import GenerateMaterialsUseCase
from src.chorus.contract import ScoreContract, score_to_contract
from src.chorus.domain.material_type import MaterialType
from src.chorus.domain.study_material import StudyMaterial
from src.chorus.web import create_chorus_web_app
from src.chorus.web.app import _build_score_from_mxl

if TYPE_CHECKING:
    from fastapi import FastAPI

    from src.osap.domain.score import Score

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"
REAL_MXL = (FIXTURES / "real_short.mxl").read_bytes()


class _RecordingUseCase(GenerateMaterialsUseCase):
    """Verifica que la web invoca el caso de uso real (no otra implementación)."""

    def __init__(self) -> None:
        super().__init__(())
        self.calls: list[tuple[MaterialType, str | None]] = []

    def generate(
        self,
        score: Score,
        material_type: MaterialType,
        voice: str | None = None,
    ) -> StudyMaterial:
        self.calls.append((material_type, voice))
        return StudyMaterial(
            material_type=material_type,
            content={"text": "material de la grabadora"},
            metadata={"title": "grabadora", "generator": "recording"},
        )


class _FailingUseCase(GenerateMaterialsUseCase):
    """Generador que falla: verifica el error controlado sin filtrar internals."""

    def __init__(self) -> None:
        super().__init__(())

    def generate(
        self,
        score: Score,
        material_type: MaterialType,
        voice: str | None = None,
    ) -> StudyMaterial:
        raise RuntimeError("detalle interno secreto")


def _real_contract() -> ScoreContract:
    """Contrato real producido a partir del `.mxl` de fixtures vía OSAP validator."""
    score = _build_score_from_mxl(REAL_MXL, title="Ave Maria")
    return score_to_contract(score)


def _client(app: FastAPI | None = None) -> TestClient:
    return TestClient(app or create_chorus_web_app())


class TestIndex:
    def test_serves_chorus_page(self) -> None:
        with _client() as client:
            response = client.get("/")
        assert response.status_code == 200
        assert "Chorus" in response.text
        assert "Generar material" in response.text


class TestGenerateContract:
    def test_material_real_desde_contrato(self) -> None:
        with _client() as client:
            response = client.post(
                "/generate",
                json=_real_contract().to_dict(),
            )
        assert response.status_code == 200
        data = response.json()
        assert data["material_type"] == "exercise"
        metadata = data["metadata"]
        assert metadata["title"] == "Ave Maria"
        assert metadata["parts"] == 1
        assert metadata["measures"] == 14
        assert metadata["notes"] == 100
        assert metadata["quality_level"] is not None
        assert isinstance(metadata.get("quality_report"), dict)
        assert data["content"]["text"] is not None

    def test_contrato_ilegible_rechazado(self) -> None:
        doc = _real_contract().to_dict()
        assert isinstance(doc["quality"], dict)
        quality = doc["quality"]
        assert isinstance(quality, dict)
        quality["level"] = 0
        with _client() as client:
            response = client.post("/generate", json=doc)
        assert response.status_code == 400
        assert "error" in response.json()

    def test_contrato_no_json_rechazado(self) -> None:
        with _client() as client:
            response = client.post(
                "/generate",
                content=b"esto no es json",
                headers={"Content-Type": "text/plain"},
            )
        assert response.status_code == 400
        assert "error" in response.json()

    def test_version_no_soportada_rechazada(self) -> None:
        doc = _real_contract().to_dict()
        doc["schema_version"] = 99
        with _client() as client:
            response = client.post("/generate", json=doc)
        assert response.status_code == 400
        assert "schema_version" in response.json()["error"]

    def test_usa_el_caso_de_uso_real(self) -> None:
        recording = _RecordingUseCase()
        with _client(create_chorus_web_app(use_case=recording)) as client:
            response = client.post("/generate", json=_real_contract().to_dict())
        assert response.status_code == 200
        assert recording.calls == [(MaterialType.EXERCISE, None)]
        assert response.json()["content"]["text"] == "material de la grabadora"

    def test_error_de_generacion_controlado_sin_detalles(self) -> None:
        with _client(create_chorus_web_app(use_case=_FailingUseCase())) as client:
            response = client.post("/generate", json=_real_contract().to_dict())
        assert response.status_code == 500
        body = response.json()
        assert "error" in body
        assert "detalle interno secreto" not in response.text

    def test_sin_cuerpo_devuelve_400(self) -> None:
        with _client() as client:
            response = client.post("/generate")
        assert response.status_code == 400


class TestGenerateFileLegacy:
    def test_fichero_mxl_real_todavia_funciona(self) -> None:
        with _client() as client:
            response = client.post(
                "/generate-file?title=Ave Maria",
                content=REAL_MXL,
                headers={"Content-Type": "application/octet-stream"},
            )
        assert response.status_code == 200
        assert response.json()["metadata"]["parts"] == 1

    def test_entrada_invalida_devuelve_400_controlado(self) -> None:
        with _client() as client:
            response = client.post(
                "/generate-file",
                content=b"esto no es un fichero musical",
                headers={"Content-Type": "application/octet-stream"},
            )
        assert response.status_code == 400
        assert "error" in response.json()

    def test_sin_contenido_devuelve_400(self) -> None:
        with _client() as client:
            response = client.post("/generate-file")
        assert response.status_code == 400
