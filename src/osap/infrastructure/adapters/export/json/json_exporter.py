from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.score import Score
from src.osap.ports.score_exporter import IScoreExporter


class JsonExporter(IScoreExporter):
    @property
    def output_format(self) -> OutputFormat:
        return OutputFormat.JSON

    def export(self, score: Score) -> MusicalSource:
        raise NotImplementedError
