"""Pruebas del circuito mínimo de Chorus (Score → StudyMaterial).

Cubre: generador funcional, use case, wiring y la prueba end-to-end con un
fichero .mxl real (Score producido por MusicXmlValidator de OSAP).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.chorus.application.use_cases.generate_materials import GenerateMaterialsUseCase
from src.chorus.bootstrap.container import Container
from src.chorus.bootstrap.wiring import wire
from src.chorus.domain.material_type import MaterialType
from src.chorus.domain.study_material import StudyMaterial
from src.chorus.infrastructure.generators.exercise_generator import ExerciseGenerator
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.value_objects import Confidence, Duration, ProviderId, SourceId
from src.osap.infrastructure.adapters.validation import BasicValidator

if TYPE_CHECKING:
    from src.osap.domain.score import Score

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"


def _score_from_mxl(name: str, title: str | None = None) -> Score:
    content = (FIXTURES / name).read_bytes()
    acquisition = AcquisitionResult(
        provider_id=ProviderId("test"),
        source=MusicalSource(
            source_id=SourceId(f"test-{name}"),
            content=content,
            format=OutputFormat.MUSICXML,
            metadata={"title": title, "composer": None},
        ),
        confidence=Confidence(1.0),
        processing_time=Duration(0.0),
        format=OutputFormat.MUSICXML,
    )
    return BasicValidator().validate(acquisition)


class TestGenerador:
    def test_genera_study_material_desde_score_real(self) -> None:
        score = _score_from_mxl("real_short.mxl", title="Ave Maria")
        material = ExerciseGenerator().generate(score, MaterialType.EXERCISE)
        assert isinstance(material, StudyMaterial)
        assert material.material_type == MaterialType.EXERCISE
        assert material.metadata["title"] == "Ave Maria"
        assert material.metadata["parts"] is not None
        assert material.metadata["measures"] is not None

    def test_usa_datos_reales_del_score(self) -> None:
        score = _score_from_mxl("real_large.mxl", title="Misa Brevis")
        material = ExerciseGenerator().generate(score, MaterialType.EXERCISE)
        text = material.content["text"]
        # Información real derivada del Score (no inventada).
        assert "Misa Brevis" in text
        assert "Compases: 441" in text
        assert "Partes: 7" in text
        assert "Calidad (QualityLevel):" in text

    def test_no_soporta_otro_tipo(self) -> None:
        score = _score_from_mxl("real_short.mxl")
        with __import__("pytest").raises(ValueError):
            ExerciseGenerator().generate(score, MaterialType.AUDIO)

    def test_quality_report_presente(self) -> None:
        score = _score_from_mxl("real_short.mxl")
        material = ExerciseGenerator().generate(score, MaterialType.EXERCISE)
        report = material.metadata.get("quality_report")
        assert isinstance(report, dict)
        assert set(report)  # dimensiones no vacías


class TestUseCase:
    def test_ejecuta_generador_registrado(self) -> None:
        use_case = GenerateMaterialsUseCase((ExerciseGenerator(),))
        score = _score_from_mxl("real_short.mxl")
        materials = use_case.execute(score, [MaterialType.EXERCISE])
        assert len(materials) == 1
        assert materials[0].material_type == MaterialType.EXERCISE

    def test_sin_generador_para_tipo_lanza_error(self) -> None:
        use_case = GenerateMaterialsUseCase((ExerciseGenerator(),))
        score = _score_from_mxl("real_short.mxl")
        with __import__("pytest").raises(ValueError):
            use_case.generate(score, MaterialType.AUDIO)

    def test_voice_pasada_al_material(self) -> None:
        use_case = GenerateMaterialsUseCase((ExerciseGenerator(),))
        score = _score_from_mxl("real_short.mxl")
        material = use_case.generate(score, MaterialType.EXERCISE, voice="soprano")
        assert material.voice == "soprano"
        assert "Voz solicitada: soprano" in material.content["text"]


class TestWiring:
    def test_container_construct_use_case_con_generador(self) -> None:
        container = wire(Container())
        use_case = container.generate_materials_use_case()
        score = _score_from_mxl("real_short.mxl")
        material = use_case.generate(score, MaterialType.EXERCISE)
        assert isinstance(material, StudyMaterial)
        assert material.metadata["generator"] == "exercise_generator"

    def test_no_quedan_notimplemented_en_el_camino(self) -> None:
        container = wire(Container())
        use_case = container.generate_materials_use_case()
        score = _score_from_mxl("real_short.mxl")
        assert use_case.generate(score, MaterialType.EXERCISE) is not None


class TestEndToEnd:
    def test_flujo_completo_mxl_score_chorus(self) -> None:
        """MusicXML real → MusicXmlValidator → Score → Chorus → StudyMaterial."""
        score = _score_from_mxl("real_short.mxl", title="Ave Maria")
        assert score.quality_level != QualityLevel.UNREADABLE

        container = wire(Container())
        use_case = container.generate_materials_use_case()
        material = use_case.generate(score, MaterialType.EXERCISE)

        assert isinstance(material, StudyMaterial)
        assert material.metadata["title"] == "Ave Maria"
        assert material.metadata["quality_level"] == score.quality_level.value
        # Contenido derivado del Score real.
        text = material.content["text"]
        assert "Título: Ave Maria" in text
        assert material.metadata["parts"] is not None
        assert material.metadata["notes"] is not None
