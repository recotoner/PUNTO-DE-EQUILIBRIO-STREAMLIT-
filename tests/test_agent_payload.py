from datetime import date, datetime
import json
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from src.engine.pe_global import calcular_punto_equilibrio_global
from src.engine.sensibilidad_pe import calcular_sensibilidad_pe
from src.models import (
    ConciliacionControllerResult,
    EERRNormalizado,
    GlobalEERRResult,
    NivelAnalisis,
    NivelResult,
    Periodo,
    PipelineResult,
    RentabilidadComercialResult,
    ValidationResult,
)
from src.reports.agent_payload import construir_payload_agente
from src.reports.pe_view import VISTA_MENSUAL, construir_vista_pe


class AgentPayloadTests(unittest.TestCase):
    def test_dag_payload_is_json_serializable_and_contains_expected_values(self):
        result = _dag_pipeline_result()
        monthly_view = construir_vista_pe(
            result.punto_equilibrio_global,
            VISTA_MENSUAL,
        )
        sensitivity = calcular_sensibilidad_pe(monthly_view)

        payload = construir_payload_agente(
            result,
            sensibilidad=sensitivity,
            vista_actual=VISTA_MENSUAL,
            variacion_ventas_pct=0,
            variacion_costo_variable_pct=0,
            variacion_gastos_fijos_pct=0,
            utilidad_objetivo=0,
            fecha_generacion=datetime(
                2026,
                6,
                15,
                10,
                30,
                tzinfo=ZoneInfo("America/Santiago"),
            ),
        )

        serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)

        self.assertTrue(serialized)
        self.assertEqual(
            payload["metadata"]["nombre_empresa"],
            "DISTRIBUIDORA DAG SPA",
        )
        self.assertEqual(payload["metadata"]["meses_periodo"], 5)
        self.assertEqual(
            payload["metadata"]["modulo"],
            "punto_equilibrio_rentabilidad",
        )
        self.assertEqual(payload["metadata"]["version_payload"], "v1")
        self.assertAlmostEqual(
            payload["punto_equilibrio"]["pe_mensual"],
            46_812_549.67,
            places=2,
        )
        self.assertAlmostEqual(
            payload["punto_equilibrio"]["pe_periodo"],
            234_062_748.37,
            places=2,
        )
        self.assertEqual(
            payload["punto_equilibrio"][
                "costo_fijo_considerado_periodo"
            ],
            89_550_781,
        )
        self.assertAlmostEqual(
            payload["punto_equilibrio"][
                "costo_fijo_considerado_mensual"
            ],
            17_910_156.2,
        )
        self.assertAlmostEqual(
            payload["punto_equilibrio"]["margen_contribucion_pct"],
            38.25930509,
        )
        self.assertAlmostEqual(
            payload["punto_equilibrio"]["ventas_mensual"],
            50_193_131.2,
        )
        self.assertEqual(
            payload["sensibilidad"]["vista_actual"],
            "promedio_mensual",
        )
        self.assertTrue(
            payload["rentabilidad_comercial"]["disponible"]
        )
        self.assertLessEqual(
            len(
                payload["rentabilidad_comercial"][
                    "top_productos_margen"
                ]
            ),
            10,
        )
        self.assertEqual(
            payload["instrucciones_agente"][0],
            "Usar exclusivamente los datos del payload.",
        )


def _dag_pipeline_result() -> PipelineResult:
    ventas = 250_965_656.0
    costo_ventas = 154_947_940.0
    gav = 32_197_549.0
    sueldos = 57_353_232.0
    eerr = EERRNormalizado(
        empresa="DISTRIBUIDORA DAG SPA",
        rut="",
        periodo=Periodo(date(2026, 1, 1), date(2026, 5, 31)),
        formato="mensual",
        cuentas=pd.DataFrame(
            [
                _account("MARGEN DE EXPLOTACION", ventas - costo_ventas),
                _account(
                    "TOTAL GASTOS DE ADMINISTRACION Y VENTAS",
                    gav,
                ),
                _account("RESULTADO OPERACIONAL", 0),
                _account("TOTAL SUELDOS Y LEYES SOCIALES", sueldos),
            ]
        ),
        totales={},
    )
    global_result = GlobalEERRResult(
        metricas={
            "ventas_eerr": ventas,
            "costo_ventas_eerr": costo_ventas,
            "margen_eerr": ventas - costo_ventas,
            "margen_eerr_pct": (ventas - costo_ventas) / ventas,
            "gastos_administracion_ventas": gav,
            "resultado_operacional": 6_466_935.0,
            "utilidad_perdida": 5_000_000.0,
        }
    )
    pe_result = calcular_punto_equilibrio_global(global_result, eerr)
    commercial_metrics = {
        "venta_neta_valida": 245_000_000.0,
        "costo_total_valido": 150_000_000.0,
        "margen_comercial": 95_000_000.0,
        "margen_comercial_pct": 95_000_000 / 245_000_000,
        "cantidad_lineas_validas": 100,
        "cantidad_lineas_excluidas": 2,
        "venta_excluida_costo_cero": 1_000_000.0,
    }
    top_products = pd.DataFrame(
        [
            {
                "SKU": f"SKU-{index}",
                "Producto": f"Producto {index}",
                "Venta neta valida": 10_000_000 - index,
                "Costo total valido": 5_000_000,
                "Margen $": 5_000_000 - index,
                "Margen %": 0.5,
                "Participacion venta valida": 0.04,
            }
            for index in range(12)
        ]
    )
    comercial = RentabilidadComercialResult(
        metricas=commercial_metrics,
        rentabilidad_por_producto=top_products,
        top_margen=top_products,
        bottom_margen_pct=top_products.iloc[0:0],
        venta_relevante_margen_bajo=top_products.iloc[0:0],
    )
    comparison = pd.DataFrame(
        [
            _comparison("Ventas", ventas, 245_000_000.0),
            _comparison("Costo de ventas", costo_ventas, 150_000_000.0),
            _comparison(
                "Margen",
                ventas - costo_ventas,
                95_000_000.0,
            ),
        ]
    )
    controller = ConciliacionControllerResult(
        metricas={},
        comparacion=comparison,
        conciliacion_fuentes=pd.DataFrame(),
        interpretacion="Lectura controller de prueba.",
    )
    validation = ValidationResult(
        warnings=["Advertencia de prueba."],
        metrics={
            "cobertura_costo_valido": 0.98,
            "lineas_excluidas_costo_cero": 2,
            "ventas_filas_fuera_periodo": 3,
            "conciliacion_costos_diferencia_pct": 0.12,
        },
    )
    return PipelineResult(
        eerr=eerr,
        ventas=None,
        validation=validation,
        nivel=NivelResult(NivelAnalisis.NIVEL_2_COMERCIAL),
        global_eerr=global_result,
        punto_equilibrio_global=pe_result,
        comercial=comercial,
        conciliacion_controller=controller,
    )


def _account(concept: str, total: float) -> dict:
    return {
        "concepto": concept,
        "concepto_clave": concept.upper(),
        "total": total,
    }


def _comparison(concept: str, eerr: float, commercial: float) -> dict:
    difference = commercial - eerr
    return {
        "Concepto": concept,
        "EERR": eerr,
        "Comercial valido": commercial,
        "Diferencia": difference,
        "Diferencia % EERR": abs(difference) / abs(eerr),
    }


if __name__ == "__main__":
    unittest.main()
