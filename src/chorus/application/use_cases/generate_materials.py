from typing import List, Optional
from src.osap.domain import Score
from src.chorus.domain import StudyMaterial, MaterialType
from src.chorus.ports import IStudyMaterialGenerator


class GenerateMaterialsUseCase:
    def __init__(self, generators: List[IStudyMaterialGenerator]):
        self.generators = generators

    def execute(self, score: Score, material_types: List[MaterialType]) -> List[StudyMaterial]:
        raise NotImplementedError

    def generate(self, score: Score, material_type: MaterialType, voice: Optional[str] = None) -> StudyMaterial:
        raise NotImplementedError
