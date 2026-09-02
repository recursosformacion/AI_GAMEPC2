from __future__ import annotations

from typing import TYPE_CHECKING

from src.chorus.ports.study_material_generator import IStudyMaterialGenerator

if TYPE_CHECKING:
    from src.chorus.domain.material_type import MaterialType
    from src.chorus.domain.study_material import StudyMaterial
    from src.osap.domain.score import Score


class PDFGenerator(IStudyMaterialGenerator):
    @property
    def name(self) -> str:
        return "pdf_generator"

    def generate(self, score: Score, material_type: MaterialType, voice: str | None = None) -> StudyMaterial:
        raise NotImplementedError
