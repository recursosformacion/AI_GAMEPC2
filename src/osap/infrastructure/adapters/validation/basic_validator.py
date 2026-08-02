from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.score import Score
from src.osap.ports.score_validator import IScoreValidator


class BasicValidator(IScoreValidator):
    @property
    def name(self) -> str:
        return "basic_validator"

    def validate(self, result: AcquisitionResult) -> Score:
        raise NotImplementedError
