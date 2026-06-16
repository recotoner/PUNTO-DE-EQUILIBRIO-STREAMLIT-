import json
from datetime import date
import unittest

import pandas as pd

from src.engine.pe_global import calcular_punto_equilibrio_global
from src.models import EERRNormalizado, GlobalEERRResult, Periodo
from src.reports.pe_global_chart import construir_grafico_pe_global
from src.reports.pe_view import (
    VISTA_MENSUAL,
    VISTA_PERIODO,
    construir_vista_pe,
)


def _account(concept: str, total: float) -> dict:
    return {
        "concepto": concept,
        "concepto_clave": concept.upper(),
        "total": total,
    }


class PuntoEquilibrioGlobalTests(unittest.TestCase):
    def test_normal_case(self):
        global_result = GlobalEERRResult(
            metricas={
                "ventas_eerr": 1000.0,
                "costo_ventas_eerr": 400.0,
                "gastos_administracion_ventas": 300.0,
            }
        )

        result = calcular_punto_equilibrio_global(global_result)

        self.assertTrue(result.calculable)
        self.assertEqual(result.metricas["margen_eerr"], 600.0)
        self.assertAlmostEqual(
            result.metricas["margen_contribucion_pct_aproximado"], 0.6
        )
        self.assertAlmostEqual(result.metricas["punto_equilibrio_ventas"], 500.0)
        self.assertAlmostEqual(result.metricas["holgura_sobre_pe"], 500.0)
        self.assertAlmostEqual(result.metricas["holgura_sobre_pe_pct"], 0.5)
        self.assertTrue(result.advertencias)

    def test_fixed_cost_composition_and_monthly_break_even(self):
        global_result = GlobalEERRResult(
            metricas={
                "ventas_eerr": 1000.0,
                "costo_ventas_eerr": 400.0,
                "gastos_administracion_ventas": 300.0,
            }
        )
        eerr = EERRNormalizado(
            empresa="Empresa prueba",
            rut="",
            periodo=Periodo(date(2026, 1, 1), date(2026, 5, 31)),
            formato="mensual",
            cuentas=pd.DataFrame(
                [
                    _account("MARGEN DE EXPLOTACION", 600),
                    _account("Honorarios Profesionales", 100),
                    _account("Gastos Generales", 200),
                    _account("TOTAL GASTOS DE ADMINISTRACION Y VENTAS", 300),
                    _account("RESULTADO OPERACIONAL", 300),
                    _account("Remuneraciones", 170),
                    _account("Leyes Sociales", 30),
                    _account("TOTAL SUELDOS Y LEYES SOCIALES", 200),
                    _account("Gastos Bancarios", 50),
                    _account("TOTAL GASTOS FINANCIEROS", 50),
                ]
            ),
            totales={},
        )

        result = calcular_punto_equilibrio_global(global_result, eerr)

        self.assertTrue(result.calculable)
        self.assertEqual(result.metricas["cantidad_meses_periodo"], 5)
        self.assertEqual(result.metricas["costo_fijo_considerado_periodo"], 500)
        self.assertEqual(result.metricas["costo_fijo_promedio_mensual"], 100)
        self.assertAlmostEqual(result.metricas["punto_equilibrio_periodo"], 500 / 0.6)
        self.assertAlmostEqual(
            result.metricas["punto_equilibrio_promedio_mensual"],
            100 / 0.6,
        )
        self.assertEqual(len(result.composicion_costo_fijo), 2)
        self.assertNotIn(
            "Gastos Bancarios",
            set(result.composicion_costo_fijo["Cuenta o subtotal incluido"]),
        )

    def test_only_gav_preserves_previous_break_even(self):
        global_result = GlobalEERRResult(
            metricas={
                "ventas_eerr": 1000.0,
                "costo_ventas_eerr": 400.0,
                "gastos_administracion_ventas": 300.0,
            }
        )
        eerr = EERRNormalizado(
            empresa="Empresa sin costos fijos adicionales",
            rut="",
            periodo=Periodo(date(2026, 1, 1), date(2026, 1, 31)),
            formato="mensual",
            cuentas=pd.DataFrame(
                [
                    _account("MARGEN DE EXPLOTACION", 600),
                    _account("Gastos Generales", 300),
                    _account("TOTAL GASTOS DE ADMINISTRACION Y VENTAS", 300),
                    _account("RESULTADO OPERACIONAL", 300),
                ]
            ),
            totales={},
        )

        result = calcular_punto_equilibrio_global(global_result, eerr)

        self.assertEqual(result.metricas["costo_fijo_considerado_periodo"], 300)
        self.assertAlmostEqual(result.metricas["punto_equilibrio_periodo"], 500)
        self.assertEqual(len(result.composicion_costo_fijo), 1)

    def test_dag_reference_values(self):
        ventas = 250_965_656.0
        costo_ventas = 154_947_940.0
        gav = 32_197_549.0
        sueldos = 57_353_232.0
        global_result = GlobalEERRResult(
            metricas={
                "ventas_eerr": ventas,
                "costo_ventas_eerr": costo_ventas,
                "gastos_administracion_ventas": gav,
            }
        )
        eerr = EERRNormalizado(
            empresa="DAG",
            rut="",
            periodo=Periodo(date(2026, 1, 1), date(2026, 5, 31)),
            formato="mensual",
            cuentas=pd.DataFrame(
                [
                    _account("MARGEN DE EXPLOTACION", ventas - costo_ventas),
                    _account("TOTAL GASTOS DE ADMINISTRACION Y VENTAS", gav),
                    _account("RESULTADO OPERACIONAL", 0),
                    _account("TOTAL SUELDOS Y LEYES SOCIALES", sueldos),
                ]
            ),
            totales={},
        )

        result = calcular_punto_equilibrio_global(global_result, eerr)

        self.assertAlmostEqual(
            result.metricas["margen_contribucion_pct_aproximado"],
            0.3825930509,
        )
        self.assertEqual(
            result.metricas["costo_fijo_considerado_periodo"],
            89_550_781,
        )
        self.assertAlmostEqual(
            result.metricas["punto_equilibrio_periodo"],
            234_062_748.37,
            places=2,
        )
        self.assertAlmostEqual(
            result.metricas["punto_equilibrio_promedio_mensual"],
            46_812_549.67,
            places=2,
        )

        monthly_view = construir_vista_pe(result, VISTA_MENSUAL)
        self.assertAlmostEqual(
            monthly_view.metricas["gastos_fijos_estimados"],
            17_910_156.2,
        )
        self.assertAlmostEqual(
            monthly_view.metricas["punto_equilibrio_ventas"],
            46_812_549.67,
            places=2,
        )
        self.assertAlmostEqual(
            monthly_view.metricas["ventas_eerr"],
            50_193_131.2,
        )
        self.assertAlmostEqual(
            monthly_view.metricas["holgura_sobre_pe"],
            3_380_581.53,
            places=2,
        )

        period_view = construir_vista_pe(result, VISTA_PERIODO)
        self.assertIs(period_view, result)

    def test_invalid_margin_does_not_calculate_break_even(self):
        global_result = GlobalEERRResult(
            metricas={
                "ventas_eerr": 1000.0,
                "costo_ventas_eerr": 1200.0,
                "gastos_administracion_ventas": 300.0,
            }
        )

        result = calcular_punto_equilibrio_global(global_result)

        self.assertFalse(result.calculable)
        self.assertLessEqual(
            result.metricas["margen_contribucion_pct_aproximado"], 0
        )
        self.assertIsNone(result.metricas["punto_equilibrio_ventas"])
        self.assertIsNone(result.metricas["holgura_sobre_pe"])
        self.assertTrue(result.advertencias)

    def test_chart_scenarios_preserve_cost_identity_and_include_break_even(self):
        global_result = GlobalEERRResult(
            metricas={
                "ventas_eerr": 1000.0,
                "costo_ventas_eerr": 400.0,
                "gastos_administracion_ventas": 300.0,
            }
        )
        result = calcular_punto_equilibrio_global(global_result)

        chart = construir_grafico_pe_global(result, points=21)

        self.assertGreaterEqual(len(chart["escenarios"]), 21)
        for scenario in chart["escenarios"]:
            self.assertAlmostEqual(
                scenario["costo_total"],
                scenario["costo_fijo"] + scenario["costo_variable"],
            )
        self.assertGreaterEqual(
            chart["punto_equilibrio_ventas"],
            0,
        )
        self.assertLessEqual(
            chart["punto_equilibrio_ventas"],
            chart["rango_max_ventas"],
        )
        serialized_options = json.dumps(chart["options"], ensure_ascii=False)
        self.assertNotIn("function(", serialized_options)
        self.assertNotIn("--x_x--0_0--", serialized_options)
        self.assertEqual(chart["options"]["xAxis"]["name"], "Ventas período MM$")
        self.assertEqual(chart["options"]["yAxis"]["name"], "Montos período MM$")
        self.assertNotIn("axisLabel", chart["options"]["xAxis"])
        self.assertNotIn("axisLabel", chart["options"]["yAxis"])

        break_even = chart["punto_equilibrio_ventas"]
        pe_scenarios = [
            scenario
            for scenario in chart["escenarios"]
            if abs(scenario["ventas_escenario"] - break_even) < 1e-9
        ]
        self.assertEqual(len(pe_scenarios), 1)
        self.assertAlmostEqual(
            pe_scenarios[0]["ventas_escenario"],
            pe_scenarios[0]["costo_total"],
            places=9,
        )

        current_sales = result.metricas["ventas_eerr"]
        current_sales_scenarios = [
            scenario
            for scenario in chart["escenarios"]
            if abs(scenario["ventas_escenario"] - current_sales) < 1e-9
        ]
        self.assertEqual(len(current_sales_scenarios), 1)

    def test_monthly_chart_uses_monthly_scale_and_labels(self):
        global_result = GlobalEERRResult(
            metricas={
                "ventas_eerr": 5000.0,
                "costo_ventas_eerr": 2000.0,
                "gastos_administracion_ventas": 1500.0,
            }
        )
        eerr = EERRNormalizado(
            empresa="Empresa prueba",
            rut="",
            periodo=Periodo(date(2026, 1, 1), date(2026, 5, 31)),
            formato="mensual",
            cuentas=pd.DataFrame(
                [
                    _account("MARGEN DE EXPLOTACION", 3000),
                    _account("TOTAL GASTOS DE ADMINISTRACION Y VENTAS", 1500),
                ]
            ),
            totales={},
        )
        result = calcular_punto_equilibrio_global(global_result, eerr)
        monthly_view = construir_vista_pe(result, VISTA_MENSUAL)

        chart = construir_grafico_pe_global(
            monthly_view,
            points=21,
            vista=VISTA_MENSUAL,
        )

        self.assertEqual(
            chart["options"]["xAxis"]["name"],
            "Ventas mensuales MM$",
        )
        self.assertEqual(
            chart["options"]["yAxis"]["name"],
            "Montos mensuales MM$",
        )
        self.assertAlmostEqual(chart["punto_equilibrio_ventas"], 500)
        self.assertAlmostEqual(chart["rango_max_ventas"], 1500)


if __name__ == "__main__":
    unittest.main()
