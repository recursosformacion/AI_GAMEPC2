from src.chorus.ports.study_material_generator import IStudyMaterialGenerator
from src.chorus.application.use_cases.generate_materials import GenerateMaterialsUseCase


class Container:
    def __init__(self) -> None:
        self._generators: list[IStudyMaterialGenerator] = []

    def register_generator(self, generator: IStudyMaterialGenerator) -> None:
        self._generators.append(generator)

    def generate_materials_use_case(self) -> GenerateMaterialsUseCase:
        raise NotImplementedError
