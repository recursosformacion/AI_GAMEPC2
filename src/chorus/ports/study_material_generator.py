from abc import ABC, abstractmethod

from src.osap.domain.score import Score
from src.chorus.domain.study_material import StudyMaterial
from src.chorus.domain.material_type import MaterialType


class IStudyMaterialGenerator(ABC):
    @abstractmethod
    def generate(self, score: Score, material_type: MaterialType, voice: str | None = None) -> StudyMaterial:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
