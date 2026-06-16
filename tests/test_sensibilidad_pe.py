import unittest

from src.engine.pe_global import calcular_punto_equilibrio_global
from src.engine.sensibilidad_pe import calcular_sensibilidad_pe
from src.models import GlobalEERRResult
from src.reports.pe_view import VISTA_MENSUAL, construir_vista_pe


def base_result(
    ventas: float = 1000.0,
    costo_variable: float = 400.0,
    gastos_fijos: float = 300.0,
):
    return calcular_punto_equilibrio_global(
        GlobalEERRResult(
            metricas={
                "ventas_eerr": ventas,
                "costo_ventas_eerr": costo_variable,
                "gastos_administracion_ventas": gastos_fijos,
            }
        )
    )


class SensibilidadPETests(unittest.TestCase):
    def test_zero_variations_reproduce_base_break_even(self):
        base = base_result()

        result = calcular_sensibilidad_pe(base)

        self.assertTrue(result.calculable)
        self.assertEqual(result.metricas["ventas_simuladas"], 1000)
        self.assertAlmostEqual(
            result.metricas["margen_contribucion_pct_simulado"], 0.6
        )
        self.assertAlmostEqual(result.metricas["punto_equilibrio_simulado"], 500)

    def test_wide_valid_scenario_and_target_profit(self):
        base = base_result()

        result = calcular_sensibilidad_pe(
            base,
            variacion_ventas_pct=3.0,
            variacion_costo_variable_pct=-0.8,
            variacion_gastos_fijos_pct=2.0,
            utilidad_operacional_objetivo=100.0,
        )

        self.assertTrue(result.calculable)
        self.assertEqual(result.metricas["ventas_simuladas"], 4000)
        self.assertAlmostEqual(
            result.metricas["ratio_costo_variable_simulado"], 0.08
        )
        self.assertEqual(result.metricas["gastos_fijos_simulados"], 900)
        self.assertAlmostEqual(
            result.metricas["punto_equilibrio_simulado"],
            1000 / 0.92,
        )

    def test_non_positive_sales_are_invalid(self):
        result = calcular_sensibilidad_pe(
            base_result(),
            variacion_ventas_pct=-1.0,
        )

        self.assertFalse(result.calculable)
        self.assertIsNone(result.metricas["punto_equilibrio_simulado"])
        self.assertTrue(any("ventas simuladas" in item for item in result.advertencias))

    def test_non_positive_margin_is_invalid(self):
        result = calcular_sensibilidad_pe(
            base_result(),
            variacion_costo_variable_pct=2.0,
        )

        self.assertFalse(result.calculable)
        self.assertLessEqual(
            result.metricas["margen_contribucion_pct_simulado"], 0
        )
        self.assertTrue(any("margen de contribución" in item for item in result.advertencias))

    def test_negative_fixed_cost_is_allowed_with_warning(self):
        base = base_result(gastos_fijos=-100)

        result = calcular_sensibilidad_pe(base)

        self.assertTrue(result.calculable)
        self.assertLess(result.metricas["gastos_fijos_simulados"], 0)
        self.assertTrue(any("no habitual" in item for item in result.advertencias))

    def test_monthly_view_scales_sensitivity_results(self):
        base = base_result(ventas=5000, costo_variable=2000, gastos_fijos=1500)
        base.metricas["cantidad_meses_periodo"] = 5
        base.metricas["costo_fijo_promedio_mensual"] = 300
        base.metricas["punto_equilibrio_promedio_mensual"] = 500
        monthly_view = construir_vista_pe(base, VISTA_MENSUAL)

        result = calcular_sensibilidad_pe(monthly_view)

        self.assertEqual(result.metricas["ventas_simuladas"], 1000)
        self.assertEqual(result.metricas["gastos_fijos_simulados"], 300)
        self.assertAlmostEqual(result.metricas["punto_equilibrio_simulado"], 500)
        self.assertAlmostEqual(result.metricas["holgura_simulada"], 500)
        self.assertAlmostEqual(
            result.metricas["resultado_operacional_simulado"],
            300,
        )


if __name__ == "__main__":
    unittest.main()
