"""Caso de uso de generación de materiales de estudio (Chorus).

Recibe un `Score` real de OSAP, ejecuta los generadores registrados que son
aplicables a los `MaterialType` solicitados y devuelve los `StudyMaterial`
producidos. Los errores de un generador se propagan de forma controlada (no
silenciosa), de modo que el circuito no enmascare fallos.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.chorus.domain.material_type import MaterialType
    from src.chorus.domain.study_material import StudyMaterial
    from src.chorus.ports.study_material_generator import IStudyMaterialGenerator
    from src.osap.domain.score import Score


class GenerateMaterialsUseCase:
    def __init__(self, generators: Sequence[IStudyMaterialGenerator]) -> None:
        self.generators = list(generators)

    def execute(self, score: Score, material_types: Sequence[MaterialType]) -> list[StudyMaterial]:
        materials: list[StudyMaterial] = []
        for material_type in material_types:
            materials.append(self.generate(score, material_type))
        return materials

    def generate(self, score: Score, material_type: MaterialType, voice: str | None = None) -> StudyMaterial:
        """Delega en el primer generador registrado que soporte el tipo solicitado.

        Si ningún generador soporta el tipo, lanza ValueError (controlado, no opaco).
        """
        for generator in self.generators:
            try:
                material = generator.generate(score, material_type, voice)
            except ValueError:
                # El generador no soporta este tipo: probar el siguiente.
                continue
            if material is not None:
                return material
        raise ValueError(f"no hay generador para el tipo {material_type.value}")
