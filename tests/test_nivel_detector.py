import unittest

from src.engine.nivel_detector import detectar_nivel
from src.models import NivelAnalisis


class NivelDetectorTests(unittest.TestCase):
    def test_decision_table(self):
        cases = [
            (
                dict(eerr_valido=True, ventas_presentes=False),
                NivelAnalisis.NIVEL_1_GLOBAL,
            ),
            (
                dict(
                    eerr_valido=True,
                    ventas_presentes=True,
                    ventas_validas=True,
                    costos_disponibles=False,
                ),
                NivelAnalisis.NIVEL_1_GLOBAL_CON_ADVERTENCIA,
            ),
            (
                dict(
                    eerr_valido=True,
                    ventas_presentes=True,
                    ventas_validas=True,
                    costos_disponibles=True,
                ),
                NivelAnalisis.NIVEL_2_COMERCIAL,
            ),
        ]
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(detectar_nivel(**arguments).nivel, expected)

    def test_invalid_eerr_has_no_level(self):
        self.assertIsNone(
            detectar_nivel(eerr_valido=False, ventas_presentes=False)
        )


if __name__ == "__main__":
    unittest.main()
