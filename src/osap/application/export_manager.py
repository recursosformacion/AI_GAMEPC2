from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.musical_source import MusicalSource
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.score import Score
from src.osap.ports.score_exporter import IScoreExporter


class ExportManager:
    """Facade over IScoreExporter adapters. Dispatches a Score to the right exporter."""

    def __init__(self, exporters: tuple[IScoreExporter, ...]) -> None:
        self._exporters = exporters

    def export(self, score: Score, output_format: OutputFormat) -> MusicalSource:
        exporter = self._find(output_format)
        return exporter.export(score)

    def supported_formats(self) -> tuple[OutputFormat, ...]:
        return tuple(exporter.output_format for exporter in self._exporters)

    def _find(self, output_format: OutputFormat) -> IScoreExporter:
        for exporter in self._exporters:
            if exporter.output_format == output_format:
                return exporter
        raise ScoreResolutionError(f"No exporter registered for format '{output_format.value}'")
