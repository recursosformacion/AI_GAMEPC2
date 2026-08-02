from src.chorus.bootstrap.container import Container
from src.chorus.infrastructure.generators import PDFGenerator, AudioGenerator, ExerciseGenerator


def wire(container: Container) -> Container:
    raise NotImplementedError
