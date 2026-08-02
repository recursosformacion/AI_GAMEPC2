from abc import ABC, abstractmethod

from ..domain.musical_source import MusicalSource
from ..domain.output_format import OutputFormat
from ..domain.score import Score


class IScoreExporter(ABC):
    """Converts a Score into a requested output format."""

    @property
    @abstractmethod
    def output_format(self) -> OutputFormat:
        raise NotImplementedError

    @abstractmethod
    def export(self, score: Score) -> MusicalSource:
        raise NotImplementedError
