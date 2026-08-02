import unittest
from src.chorus.domain import StudyMaterial, MaterialType


class TestStudyMaterial(unittest.TestCase):
    def test_create_material(self):
        material = StudyMaterial(
            material_type=MaterialType.REDUCED_SCORE,
            content={},
        )
        self.assertEqual(material.material_type, MaterialType.REDUCED_SCORE)


if __name__ == "__main__":
    unittest.main()
