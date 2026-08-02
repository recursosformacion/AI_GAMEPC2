from src.chorus.domain.study_material import StudyMaterial


class PDFExporter:
    def export(self, material: StudyMaterial) -> bytes:
        raise NotImplementedError
