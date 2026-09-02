from src.chorus.bootstrap.container import Container


def wire(container: Container) -> Container:
    """Registra los generadores funcionales de Chorus.

    Solo se registran generadores reales y ejecutables. `AudioGenerator` y
    `PDFGenerator` siguen sin implementar (funcionalidad futura) y NO se registran
    para no crear una falsa sensación de soporte.
    """
    from src.chorus.infrastructure.generators.exercise_generator import ExerciseGenerator

    container.register_generator(ExerciseGenerator())
    return container
