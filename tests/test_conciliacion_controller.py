import unittest

from src.engine.conciliacion_controller import interpretar_conciliacion_controller


class ConciliacionControllerInterpretationTests(unittest.TestCase):
    def test_material_cost_difference_uses_conditional_generic_reading(self):
        text = interpretar_conciliacion_controller(
            diferencia_ventas_pct=0.01,
            diferencia_costos_pct=0.19,
            diferencia_margen=6_500_000,
            cobertura_costo_valido=0.965,
            lineas_excluidas_costo_cero=60,
            venta_excluida_costo_cero=5_890_988,
        )

        self.assertIn("ventas del detalle concilian razonablemente", text)
        self.assertIn("brecha material", text)
        self.assertIn("podría estar relacionada", text)
        self.assertIn("diferencias de valorización", text)
        self.assertIn("no debe interpretarse automáticamente como error", text)
        self.assertIn("revisar la composición del costo de ventas contable", text)

    def test_non_material_cost_difference_uses_soft_reading(self):
        text = interpretar_conciliacion_controller(
            diferencia_ventas_pct=0.01,
            diferencia_costos_pct=0.05,
            diferencia_margen=100_000,
            cobertura_costo_valido=0.99,
            lineas_excluidas_costo_cero=2,
            venta_excluida_costo_cero=20_000,
        )

        self.assertIn("ventas del detalle concilian razonablemente", text)
        self.assertIn("no presenta diferencias materiales relevantes", text)
        self.assertIn("no como reemplazo automático del margen contable", text)
        self.assertNotIn("Existe una brecha material", text)


if __name__ == "__main__":
    unittest.main()
