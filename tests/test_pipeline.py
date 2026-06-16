from io import BytesIO
from pathlib import Path
import unittest

import pandas as pd

from src.models import NivelAnalisis
from src.pipeline import procesar_archivos
from src.engine.rentabilidad_comercial import obtener_base_rentabilidad


ROOT = Path(__file__).resolve().parents[1]
EERR = ROOT / "estadoResultado (52).xlsx"
VENTAS = ROOT / "informeventas_12-06-2026 13_59_12.xlsx"


class PipelineTests(unittest.TestCase):
    def test_eerr_without_sales_enables_level_1(self):
        result = procesar_archivos(EERR)

        self.assertTrue(result.validation.valid)
        self.assertEqual(result.nivel.nivel, NivelAnalisis.NIVEL_1_GLOBAL)
        self.assertIsNotNone(result.global_eerr)
        self.assertEqual(result.global_eerr.metricas["ventas_eerr"], 171347531)
        self.assertEqual(result.global_eerr.metricas["margen_eerr"], 102534572)
        self.assertEqual(result.global_eerr.metricas["utilidad_perdida"], -6632420)
        self.assertIsNotNone(result.punto_equilibrio_global)
        self.assertTrue(result.punto_equilibrio_global.calculable)
        self.assertEqual(
            result.punto_equilibrio_global.metricas["cantidad_meses_periodo"],
            5,
        )
        self.assertEqual(
            result.punto_equilibrio_global.metricas[
                "costo_fijo_considerado_periodo"
            ],
            108344065,
        )
        self.assertEqual(len(result.punto_equilibrio_global.composicion_costo_fijo), 2)
        self.assertIsNone(result.comercial)
        self.assertIsNone(result.conciliacion_controller)

    def test_real_files_enable_level_2_with_warnings(self):
        result = procesar_archivos(EERR, VENTAS)

        self.assertTrue(result.validation.valid)
        self.assertEqual(result.nivel.nivel, NivelAnalisis.NIVEL_2_COMERCIAL)
        self.assertIsNotNone(result.global_eerr)
        self.assertIsNotNone(result.comercial)
        self.assertIsNotNone(result.conciliacion_controller)
        self.assertEqual(result.ventas.filas_analizadas, 2236)
        self.assertEqual(result.ventas.filas_fuera_periodo, 4959)
        self.assertEqual(result.validation.metrics["costos_cero_filas"], 60)
        self.assertEqual(result.validation.metrics["cost_validation_schema"], 2)
        self.assertEqual(
            result.validation.metrics["lineas_excluidas_costo_cero"],
            60,
        )
        self.assertEqual(len(result.ventas.datos_excluidos_costo), 60)
        self.assertEqual(
            len(result.ventas.datos_rentabilidad),
            result.validation.metrics["lineas_con_costo_valido"],
        )
        self.assertEqual(
            len(obtener_base_rentabilidad(result.ventas)),
            result.validation.metrics["lineas_con_costo_valido"],
        )
        self.assertAlmostEqual(
            result.validation.metrics["venta_total_analizada"],
            result.validation.metrics["venta_con_costo_valido"]
            + result.validation.metrics["venta_excluida_costo_cero"],
            places=6,
        )
        self.assertEqual(
            result.comercial.metricas["venta_neta_valida"],
            result.validation.metrics["venta_con_costo_valido"],
        )
        self.assertEqual(
            result.comercial.metricas["costo_total_valido"],
            result.ventas.datos_rentabilidad["Costo Venta Total"].sum(),
        )
        self.assertEqual(
            result.comercial.metricas["margen_comercial"],
            result.comercial.metricas["venta_neta_valida"]
            - result.comercial.metricas["costo_total_valido"],
        )
        self.assertEqual(len(result.comercial.top_margen), 10)
        self.assertEqual(len(result.comercial.bottom_margen_pct), 10)
        self.assertEqual(
            result.conciliacion_controller.metricas["margen_eerr"],
            result.global_eerr.metricas["margen_eerr"],
        )
        self.assertEqual(
            result.conciliacion_controller.metricas["margen_comercial_valido"],
            result.comercial.metricas["margen_comercial"],
        )
        self.assertAlmostEqual(
            result.conciliacion_controller.metricas["diferencia_margen"],
            result.comercial.metricas["margen_comercial"]
            - result.global_eerr.metricas["margen_eerr"],
        )
        self.assertEqual(
            list(result.conciliacion_controller.comparacion["Concepto"]),
            ["Ventas", "Costo de ventas", "Margen"],
        )
        self.assertGreater(
            result.validation.metrics["cobertura_costo_no_cero"],
            0.95,
        )
        zero_summary = result.validation.metrics["costos_cero_resumen"]
        classification_summary = result.validation.metrics[
            "costos_cero_resumen_clasificacion"
        ]
        self.assertEqual(int(zero_summary["Filas"].sum()), 60)
        self.assertEqual(len(classification_summary), 3)
        self.assertEqual(int(classification_summary["Filas"].sum()), 60)
        self.assertIn(
            "Posible servicio / despacho / recargo / ítem no inventariable",
            set(zero_summary["Clasificacion"]),
        )
        self.assertIn(
            "Producto con costo cero que requiere revisión",
            set(zero_summary["Clasificacion"]),
        )
        self.assertIn(
            "Nota de crédito o ajuste legítimo",
            set(zero_summary["Clasificacion"]),
        )
        self.assertAlmostEqual(
            result.validation.metrics["conciliacion_costos_diferencia_pct"],
            0.1922325,
            places=6,
        )
        self.assertTrue(
            any("diferencia de costos" in warning for warning in result.validation.warnings)
        )
        self.assertTrue(
            any(
                warning.startswith("Se detectaron líneas con costo cero")
                for warning in result.validation.warnings
            )
        )

    def test_sales_without_cost_columns_falls_back_to_level_1_warning(self):
        sales_file = BytesIO()
        pd.DataFrame(
            {
                "Fecha": ["15/01/2026"],
                "Total Linea": [1000],
                "Cantidad": [1],
            }
        ).to_excel(sales_file, index=False, engine="openpyxl")
        sales_file.seek(0)

        result = procesar_archivos(EERR, sales_file)

        self.assertFalse(result.validation.valid)
        self.assertEqual(
            result.nivel.nivel,
            NivelAnalisis.NIVEL_1_GLOBAL_CON_ADVERTENCIA,
        )
        self.assertTrue(any("columnas de costo" in error for error in result.validation.errors))
        self.assertIsNone(result.comercial)

    def test_all_zero_costs_do_not_provide_sufficient_coverage(self):
        sales_file = BytesIO()
        pd.DataFrame(
            {
                "Fecha": ["15/01/2026", "16/01/2026"],
                "Documento": ["Factura Electronica", "Factura Electronica"],
                "Producto": ["Producto A", "DESPACHO"],
                "SKU": ["A", "DESP"],
                "Total Linea": [1000, 500],
                "Costo Venta Unitario": [0, 0],
                "Costo Venta Total": [0, 0],
                "Cantidad": [1, 1],
            }
        ).to_excel(sales_file, index=False, engine="openpyxl")
        sales_file.seek(0)

        result = procesar_archivos(EERR, sales_file)

        self.assertEqual(
            result.nivel.nivel,
            NivelAnalisis.NIVEL_1_GLOBAL_CON_ADVERTENCIA,
        )
        self.assertFalse(result.validation.metrics["costos_disponibles"])
        self.assertTrue(
            any("cobertura de costos" in error for error in result.validation.errors)
        )

    def test_zero_unit_cost_excludes_line_even_when_total_cost_is_non_zero(self):
        sales_file = BytesIO()
        pd.DataFrame(
            {
                "Fecha": ["15/01/2026", "16/01/2026"],
                "Documento": ["Factura Electronica", "Factura Electronica"],
                "Producto": ["Producto sin costo unitario", "Producto valido"],
                "SKU": ["A", "B"],
                "Total Linea": [1000, 2000],
                "Costo Venta Unitario": [0, 500],
                "Costo Venta Total": [700, 500],
                "Cantidad": [1, 1],
            }
        ).to_excel(sales_file, index=False, engine="openpyxl")
        sales_file.seek(0)

        result = procesar_archivos(EERR, sales_file)

        self.assertEqual(result.validation.metrics["lineas_excluidas_costo_cero"], 1)
        self.assertEqual(result.validation.metrics["venta_total_analizada"], 3000)
        self.assertEqual(result.validation.metrics["venta_con_costo_valido"], 2000)
        self.assertEqual(result.validation.metrics["venta_excluida_costo_cero"], 1000)
        self.assertEqual(len(result.ventas.datos_rentabilidad), 1)
        self.assertEqual(len(result.ventas.datos_excluidos_costo), 1)

    def test_same_sku_keeps_valid_lines_and_reports_excluded_lines(self):
        sales_file = BytesIO()
        pd.DataFrame(
            {
                "Fecha": ["15/01/2026", "16/01/2026", "17/01/2026"],
                "Documento": [
                    "Factura Electronica",
                    "Factura Electronica",
                    "Factura Electronica",
                ],
                "Producto": ["Producto X", "Producto X", "Producto X"],
                "SKU": ["SKU-X", "SKU-X", "SKU-X"],
                "Total Linea": [1000, 500, 2000],
                "Costo Venta Unitario": [600, 0, 500],
                "Costo Venta Total": [600, 0, 1000],
                "Cantidad": [1, 1, 2],
            }
        ).to_excel(sales_file, index=False, engine="openpyxl")
        sales_file.seek(0)

        result = procesar_archivos(EERR, sales_file)

        self.assertEqual(result.nivel.nivel, NivelAnalisis.NIVEL_2_COMERCIAL)
        self.assertIsNotNone(result.comercial)
        product = result.comercial.rentabilidad_por_producto.iloc[0]
        self.assertEqual(product["SKU"], "SKU-X")
        self.assertEqual(product["Cantidad vendida valida"], 3)
        self.assertEqual(product["Venta neta valida"], 3000)
        self.assertEqual(product["Costo total valido"], 1600)
        self.assertEqual(product["Margen $"], 1400)
        self.assertAlmostEqual(product["Margen %"], 1400 / 3000)
        self.assertEqual(product["Lineas excluidas mismo SKU"], 1)
        self.assertEqual(product["Venta excluida mismo SKU"], 500)


if __name__ == "__main__":
    unittest.main()
