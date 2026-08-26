from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.score import Score
from src.osap.infrastructure.validation.musicxml_validator import MusicXmlValidator
from src.osap.ports.score_validator import IScoreValidator


class BasicValidator(IScoreValidator):
    """Validador por defecto: delega en el validador MusicXML por niveles.

    El `AcquisitionResult` debe llevar el contenido MusicXML (o .mxl) en
    `result.source.content` y `result.format == MUSICXML`.
    """

    @property
    def name(self) -> str:
        return "basic_validator"

    def validate(self, result: AcquisitionResult) -> Score:
        return MusicXmlValidator().validate(result)
