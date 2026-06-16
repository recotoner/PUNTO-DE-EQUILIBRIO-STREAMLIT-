from pathlib import Path
import unittest

from src.adapters import VentasAdapter, cargar_eerr


ROOT = Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def test_monthly_eerr(self):
        eerr = cargar_eerr(ROOT / "estadoResultado (52).xlsx")

        self.assertEqual(eerr.formato, "mensual")
        self.assertEqual(eerr.periodo.fecha_inicio.isoformat(), "2026-01-01")
        self.assertEqual(eerr.periodo.fecha_fin.isoformat(), "2026-05-31")
        self.assertEqual(eerr.totales["TOTAL INGRESOS DE EXPLOTACION"], 171347531)
        self.assertEqual(len(eerr.meses), 5)

    def test_accumulated_eerr(self):
        eerr = cargar_eerr(ROOT / "estadoResultado (53).xlsx")

        self.assertEqual(eerr.formato, "acumulado")
        self.assertEqual(eerr.meses, [])
        self.assertEqual(eerr.totales["TOTAL COSTOS DE EXPLOTACION"], 68812959)

    def test_sales_adapter(self):
        ventas = VentasAdapter().load(
            ROOT / "informeventas_12-06-2026 13_59_12.xlsx"
        )

        self.assertEqual(ventas.filas_originales, 7195)
        self.assertEqual(ventas.periodo_original.fecha_inicio.isoformat(), "2025-06-13")
        self.assertEqual(ventas.periodo_original.fecha_fin.isoformat(), "2026-06-11")
        self.assertTrue(ventas.tiene_columnas_costo)


if __name__ == "__main__":
    unittest.main()
