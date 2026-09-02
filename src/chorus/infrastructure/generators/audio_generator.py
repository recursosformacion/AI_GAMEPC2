from src.chorus.domain.material_type import MaterialType
from src.chorus.domain.study_material import StudyMaterial
from src.chorus.ports.study_material_generator import IStudyMaterialGenerator
from src.osap.domain.score import Score


class AudioGenerator(IStudyMaterialGenerator):
    @property
    def name(self) -> str:
        return "audio_generator"

    def generate(self, score: Score, material_type: MaterialType, voice: str | None = None) -> StudyMaterial:
        raise NotImplementedError
