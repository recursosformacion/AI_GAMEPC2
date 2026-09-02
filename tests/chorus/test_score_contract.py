"""Tests del contrato serializable `Score` (frontera OSAP → Chorus).

Cubren: serialización/deserialización, round-trip con `.mxl` real, equivalencia
funcional ante `ExerciseGenerator`, rechazo de contratos inválidos e incompatibles,
y la independencia del contrato respecto a clases Python de OSAP.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.chorus.application.use_cases.generate_materials import GenerateMaterialsUseCase
from src.chorus.contract import (
    ContractError,
    ScoreContract,
    contract_to_score,
    score_to_contract,
)
from src.chorus.domain.material_type import MaterialType
from src.chorus.domain.study_material import StudyMaterial
from src.chorus.infrastructure.generators.exercise_generator import ExerciseGenerator
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import Confidence, Duration, ProviderId, SourceId
from src.osap.infrastructure.adapters.validation import BasicValidator

if TYPE_CHECKING:
    from src.osap.domain.score import Score

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"
REAL_MXL = (FIXTURES / "real_short.mxl").read_bytes()


def _real_score() -> Score:
    acquisition = AcquisitionResult(
        provider_id=ProviderId("test"),
        source=MusicalSource(
            source_id=SourceId("score-contract-fixture"),
            content=REAL_MXL,
            format=OutputFormat.MUSICXML,
            metadata={"title": "Ave Maria", "composer": None},
        ),
        confidence=Confidence(1.0),
        processing_time=Duration(0.0),
        format=OutputFormat.MUSICXML,
    )
    return BasicValidator().validate(acquisition)


class TestSerializacion:
    def test_score_a_contrato_representa_obra_validada(self) -> None:
        score = _real_score()
        contract = score_to_contract(score)
        assert contract.title == "Ave Maria"
        assert contract.schema_version == 1
        assert contract.quality is not None and contract.quality.level >= 1
        assert contract.structure is not None
        assert contract.structure.parts == 1
        assert contract.structure.measures == 14
        assert contract.structure.notes == 100
        assert contract.structure.voices == 1
        assert contract.structure.has_lyrics is False
        assert contract.quality is not None
        assert contract.quality.report.get("structure") == 1.0
        assert contract.quality.report.get("notation") == 0.9

    def test_to_dict_from_dict_roundtrip(self) -> None:
        contract = score_to_contract(_real_score())
        restored = ScoreContract.from_dict(contract.to_dict())
        assert restored == contract

    def test_to_json_from_json_roundtrip(self) -> None:
        contract = score_to_contract(_real_score())
        restored = ScoreContract.from_json(contract.to_json())
        assert restored == contract


class TestDeserializacion:
    def test_contrato_a_score_equivalente(self) -> None:
        contract = score_to_contract(_real_score())
        score = contract_to_score(contract)
        assert score.title == "Ave Maria"
        assert score.metadata["parts"] == 1
        assert score.metadata["measures"] == 14
        assert score.metadata["notes"] == 100
        assert score.metadata["has_lyrics"] is False
        assert score.metadata["valid"] is True

    def test_roundtrip_equivalencia_funcional(self) -> None:
        original = _real_score()
        generator = ExerciseGenerator()
        use_case = GenerateMaterialsUseCase((generator,))
        material_a = use_case.generate(original, MaterialType.EXERCISE)

        contract = score_to_contract(original)
        restored = contract_to_score(ScoreContract.from_json(contract.to_json()))
        material_b = use_case.generate(restored, MaterialType.EXERCISE)

        assert isinstance(material_a, StudyMaterial)
        assert isinstance(material_b, StudyMaterial)
        assert material_a.material_type == material_b.material_type
        assert material_a.content == material_b.content
        assert material_a.metadata == material_b.metadata


class TestContratosInvalidos:
    def test_documento_no_objeto(self) -> None:
        with pytest.raises(ContractError):
            ScoreContract.from_dict([1, 2, 3])

    def test_falta_schema_version(self) -> None:
        with pytest.raises(ContractError):
            ScoreContract.from_dict({"title": "X"})

    def test_version_no_soportada(self) -> None:
        with pytest.raises(ContractError, match="schema_version"):
            ScoreContract.from_dict({"schema_version": 2})

    def test_faltan_structure_y_quality(self) -> None:
        with pytest.raises(ContractError):
            ScoreContract.from_dict({"schema_version": 1, "title": "X"})

    def test_quality_reporte_fuera_de_rango(self) -> None:
        with pytest.raises(ContractError):
            ScoreContract.from_dict(
                {
                    "schema_version": 1,
                    "structure": {"parts": 1},
                    "quality": {"level": 2, "report": {"structure": 5.0}},
                }
            )

    def test_json_invalido(self) -> None:
        with pytest.raises(ContractError):
            ScoreContract.from_json("no es json")


class TestIndependencia:
    def test_importar_contrato_no_carga_osap(self) -> None:
        code = (
            "import src.chorus.contract as c; "
            "import sys; "
            "print(any(m.startswith('src.osap') for m in sys.modules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(__file__).resolve().parents[2],
        )
        assert result.stdout.strip() == "False"
