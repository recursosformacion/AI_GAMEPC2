from src.osap.domain.score import Score
from src.chorus.domain.study_material import StudyMaterial
from src.chorus.domain.material_type import MaterialType
from src.chorus.ports.study_material_generator import IStudyMaterialGenerator


class ExerciseGenerator(IStudyMaterialGenerator):
    @property
    def name(self) -> str:
        return "exercise_generator"

    def generate(self, score: Score, material_type: MaterialType, voice: str | None = None) -> StudyMaterial:
        raise NotImplementedError
