from src.chorus.application.use_cases.generate_materials import GenerateMaterialsUseCase
from src.chorus.ports.study_material_generator import IStudyMaterialGenerator


class Container:
    def __init__(self) -> None:
        self._generators: list[IStudyMaterialGenerator] = []

    def register_generator(self, generator: IStudyMaterialGenerator) -> None:
        self._generators.append(generator)

    def generate_materials_use_case(self) -> GenerateMaterialsUseCase:
        return GenerateMaterialsUseCase(tuple(self._generators))
