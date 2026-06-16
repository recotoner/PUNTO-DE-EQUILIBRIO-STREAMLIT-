"""Structured payload builder for the future n8n analysis agent."""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from src.config import COST_RECONCILIATION_TOLERANCE
from src.models import PipelineResult, SensibilidadPEResult
from .pe_view import VISTA_MENSUAL

AGENT_INSTRUCTIONS = [
    "Usar exclusivamente los datos del payload.",
    "No inventar cifras ni causas no contenidas en el payload.",
    "No reemplazar el criterio del controller.",
    "Redactar en tono gerencial Kappo, claro, prudente y ejecutivo.",
    "Diferenciar siempre entre valores mensuales y valores del período acumulado.",
    "Si existen advertencias de calidad de datos, mencionarlas como limitaciones.",
]


def construir_payload_agente(
    result: PipelineResult,
    *,
    sensibilidad: SensibilidadPEResult | None,
    vista_actual: str,
    variacion_ventas_pct: float,
    variacion_costo_variable_pct: float,
    variacion_gastos_fijos_pct: float,
    utilidad_objetivo: float,
    fecha_generacion: datetime | None = None,
) -> dict[str, Any]:
    if result.eerr is None or result.global_eerr is None:
        raise ValueError("El payload requiere un EERR normalizado y su resumen global.")
    if result.punto_equilibrio_global is None:
        raise ValueError("El payload requiere el resultado de punto de equilibrio.")

    generated_at = fecha_generacion or datetime.now(
        ZoneInfo("America/Santiago")
    )
    global_metrics = result.global_eerr.metricas
    pe_result = result.punto_equilibrio_global
    pe_metrics = pe_result.metricas
    months = max(int(pe_metrics.get("cantidad_meses_periodo") or 1), 1)

    payload = {
        "metadata": {
            "nombre_empresa": result.eerr.empresa,
            "periodo_inicio": result.eerr.periodo.fecha_inicio.isoformat(),
            "periodo_fin": result.eerr.periodo.fecha_fin.isoformat(),
            "meses_periodo": months,
            "formato_eerr": result.eerr.formato,
            "nivel_habilitado": (
                result.nivel.nivel.value if result.nivel is not None else None
            ),
            "fecha_generacion": generated_at.isoformat(timespec="seconds"),
            "modulo": "punto_equilibrio_rentabilidad",
            "version_payload": "v1",
        },
        "eerr_global": {
            "ventas_eerr": _number(global_metrics.get("ventas_eerr")),
            "costo_ventas_eerr": _number(
                global_metrics.get("costo_ventas_eerr")
            ),
            "margen_eerr": _number(global_metrics.get("margen_eerr")),
            "margen_eerr_pct": _percentage(
                global_metrics.get("margen_eerr_pct")
            ),
            "gastos_administracion_ventas": _number(
                global_metrics.get("gastos_administracion_ventas")
            ),
            "resultado_operacional": _number(
                global_metrics.get("resultado_operacional")
            ),
            "utilidad_perdida": _number(
                global_metrics.get("utilidad_perdida")
            ),
        },
        "punto_equilibrio": _break_even_payload(pe_result, months),
        "sensibilidad": _sensitivity_payload(
            sensibilidad,
            vista_actual=vista_actual,
            variacion_ventas_pct=variacion_ventas_pct,
            variacion_costo_variable_pct=variacion_costo_variable_pct,
            variacion_gastos_fijos_pct=variacion_gastos_fijos_pct,
            utilidad_objetivo=utilidad_objetivo,
        ),
        "rentabilidad_comercial": _commercial_payload(result),
        "conciliacion": _reconciliation_payload(result),
        "advertencias": _warnings_payload(result, sensibilidad),
        "instrucciones_agente": AGENT_INSTRUCTIONS.copy(),
    }
    return _json_value(payload)


def _break_even_payload(result, months: int) -> dict[str, Any]:
    metrics = result.metricas
    period_sales = _number(metrics.get("ventas_eerr"))
    period_buffer = _number(metrics.get("holgura_sobre_pe_periodo"))
    composition = []
    for row in result.composicion_costo_fijo.to_dict(orient="records"):
        amount = _number(row.get("Monto del período"))
        composition.append(
            {
                "cuenta_o_subtotal": row.get("Cuenta o subtotal incluido"),
                "monto_periodo": amount,
                "monto_mensual": amount / months if amount is not None else None,
                "criterio_inclusion": row.get("Criterio de inclusión"),
            }
        )

    return {
        "vista_default": "promedio_mensual",
        "margen_contribucion_pct": _percentage(
            metrics.get("margen_contribucion_pct_aproximado")
        ),
        "costo_fijo_considerado_periodo": _number(
            metrics.get("costo_fijo_considerado_periodo")
        ),
        "costo_fijo_considerado_mensual": _number(
            metrics.get("costo_fijo_promedio_mensual")
        ),
        "pe_periodo": _number(metrics.get("punto_equilibrio_periodo")),
        "pe_mensual": _number(
            metrics.get("punto_equilibrio_promedio_mensual")
        ),
        "ventas_periodo": period_sales,
        "ventas_mensual": (
            period_sales / months if period_sales is not None else None
        ),
        "holgura_periodo": period_buffer,
        "holgura_mensual": (
            period_buffer / months if period_buffer is not None else None
        ),
        "holgura_periodo_pct": _percentage(
            metrics.get("holgura_sobre_pe_pct")
        ),
        "holgura_mensual_pct": _percentage(
            metrics.get("holgura_sobre_pe_pct")
        ),
        "composicion_costo_fijo": composition,
    }


def _sensitivity_payload(
    sensibilidad: SensibilidadPEResult | None,
    *,
    vista_actual: str,
    variacion_ventas_pct: float,
    variacion_costo_variable_pct: float,
    variacion_gastos_fijos_pct: float,
    utilidad_objetivo: float,
) -> dict[str, Any]:
    metrics = sensibilidad.metricas if sensibilidad is not None else {}
    return {
        "vista_actual": (
            "promedio_mensual"
            if vista_actual == VISTA_MENSUAL
            else "periodo_acumulado"
        ),
        "variacion_ventas_pct": _number(variacion_ventas_pct),
        "variacion_costo_variable_pct": _number(
            variacion_costo_variable_pct
        ),
        "variacion_gastos_fijos_pct": _number(variacion_gastos_fijos_pct),
        "utilidad_objetivo": _number(utilidad_objetivo),
        "ventas_simuladas": _number(metrics.get("ventas_simuladas")),
        "margen_contribucion_simulado_pct": _percentage(
            metrics.get("margen_contribucion_pct_simulado")
        ),
        "costo_fijo_simulado": _number(
            metrics.get("gastos_fijos_simulados")
        ),
        "ventas_requeridas": _number(
            metrics.get("punto_equilibrio_simulado")
        ),
        "holgura_simulada": _number(metrics.get("holgura_simulada")),
        "resultado_operacional_simulado": _number(
            metrics.get("resultado_operacional_simulado")
        ),
    }


def _commercial_payload(result: PipelineResult) -> dict[str, Any]:
    if result.comercial is None:
        return {
            "disponible": False,
            "venta_neta_valida": None,
            "costo_total_valido": None,
            "margen_comercial": None,
            "margen_comercial_pct": None,
            "lineas_validas": None,
            "lineas_excluidas": None,
            "venta_excluida_costo_cero": None,
            "cobertura_costo_valido_pct": _percentage(
                result.validation.metrics.get("cobertura_costo_valido")
            ),
            "top_productos_margen": [],
        }

    metrics = result.comercial.metricas
    products = []
    for row in result.comercial.top_margen.head(10).to_dict(orient="records"):
        products.append(
            {
                "sku": row.get("SKU"),
                "producto": row.get("Producto"),
                "venta_neta_valida": _number(row.get("Venta neta valida")),
                "costo_total_valido": _number(row.get("Costo total valido")),
                "margen": _number(row.get("Margen $")),
                "margen_pct": _percentage(row.get("Margen %")),
                "participacion_venta_valida_pct": _percentage(
                    row.get("Participacion venta valida")
                ),
            }
        )
    return {
        "disponible": True,
        "venta_neta_valida": _number(metrics.get("venta_neta_valida")),
        "costo_total_valido": _number(metrics.get("costo_total_valido")),
        "margen_comercial": _number(metrics.get("margen_comercial")),
        "margen_comercial_pct": _percentage(
            metrics.get("margen_comercial_pct")
        ),
        "lineas_validas": _integer(metrics.get("cantidad_lineas_validas")),
        "lineas_excluidas": _integer(
            metrics.get("cantidad_lineas_excluidas")
        ),
        "venta_excluida_costo_cero": _number(
            metrics.get("venta_excluida_costo_cero")
        ),
        "cobertura_costo_valido_pct": _percentage(
            result.validation.metrics.get("cobertura_costo_valido")
        ),
        "top_productos_margen": products,
    }


def _reconciliation_payload(result: PipelineResult) -> dict[str, Any]:
    if result.conciliacion_controller is None:
        return {
            "ventas_eerr": None,
            "ventas_comercial_valido": None,
            "diferencia_ventas": None,
            "diferencia_ventas_pct": None,
            "costo_ventas_eerr": None,
            "costo_comercial_valido": None,
            "diferencia_costo": None,
            "diferencia_costo_pct": None,
            "margen_eerr": None,
            "margen_comercial_valido": None,
            "diferencia_margen": None,
            "diferencia_margen_pct": None,
            "lectura_controller_actual": None,
        }

    controller = result.conciliacion_controller
    rows = {
        row["Concepto"]: row
        for row in controller.comparacion.to_dict(orient="records")
    }
    sales = rows.get("Ventas", {})
    costs = rows.get("Costo de ventas", {})
    margin = rows.get("Margen", {})
    return {
        "ventas_eerr": _number(sales.get("EERR")),
        "ventas_comercial_valido": _number(sales.get("Comercial valido")),
        "diferencia_ventas": _number(sales.get("Diferencia")),
        "diferencia_ventas_pct": _percentage(
            sales.get("Diferencia % EERR")
        ),
        "costo_ventas_eerr": _number(costs.get("EERR")),
        "costo_comercial_valido": _number(costs.get("Comercial valido")),
        "diferencia_costo": _number(costs.get("Diferencia")),
        "diferencia_costo_pct": _percentage(
            costs.get("Diferencia % EERR")
        ),
        "margen_eerr": _number(margin.get("EERR")),
        "margen_comercial_valido": _number(
            margin.get("Comercial valido")
        ),
        "diferencia_margen": _number(margin.get("Diferencia")),
        "diferencia_margen_pct": _percentage(
            margin.get("Diferencia % EERR")
        ),
        "lectura_controller_actual": controller.interpretacion,
    }


def _warnings_payload(
    result: PipelineResult,
    sensibilidad: SensibilidadPEResult | None,
) -> dict[str, Any]:
    messages = [
        *result.validation.errors,
        *result.validation.warnings,
        *(result.nivel.advertencias if result.nivel is not None else []),
        *(
            result.punto_equilibrio_global.advertencias
            if result.punto_equilibrio_global is not None
            else []
        ),
        *(sensibilidad.advertencias if sensibilidad is not None else []),
    ]
    unique_messages = list(dict.fromkeys(messages))
    metrics = result.validation.metrics
    cost_difference = abs(
        float(metrics.get("conciliacion_costos_diferencia_pct") or 0)
    )
    return {
        "lista": unique_messages,
        "costos_cero_detectados": bool(
            metrics.get("lineas_excluidas_costo_cero", 0)
        ),
        "filas_fuera_periodo": _integer(
            metrics.get("ventas_filas_fuera_periodo")
        )
        or 0,
        "diferencia_costos_material": (
            cost_difference > COST_RECONCILIATION_TOLERANCE
        ),
        "notas_limitaciones": [
            "El punto de equilibrio es una aproximación operacional basada en el EERR.",
            "El costo fijo considerado requiere revisión del controller.",
            "La rentabilidad comercial utiliza únicamente líneas con costo válido informado.",
        ],
    }


def _percentage(value: Any) -> float | None:
    number = _number(value)
    return number * 100 if number is not None else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, bool, int)) or value is None:
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    return str(value)
