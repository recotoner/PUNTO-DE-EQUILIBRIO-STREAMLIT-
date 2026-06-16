"""Presentation views for period and monthly break-even values."""

from __future__ import annotations

from dataclasses import replace

from src.models import PuntoEquilibrioGlobalResult

VISTA_MENSUAL = "Promedio mensual"
VISTA_PERIODO = "Período acumulado"

_SCALABLE_METRICS = (
    "ventas_eerr",
    "costo_ventas_eerr",
    "margen_eerr",
    "gastos_fijos_estimados",
    "costo_fijo_considerado_periodo",
    "punto_equilibrio_ventas",
    "punto_equilibrio_periodo",
    "holgura_sobre_pe",
    "holgura_sobre_pe_periodo",
)


def construir_vista_pe(
    result: PuntoEquilibrioGlobalResult,
    vista: str,
) -> PuntoEquilibrioGlobalResult:
    if vista == VISTA_PERIODO:
        return result
    if vista != VISTA_MENSUAL:
        raise ValueError(f"Vista de punto de equilibrio no soportada: {vista}")

    months = max(float(result.metricas.get("cantidad_meses_periodo") or 1), 1)
    metrics = dict(result.metricas)
    for key in _SCALABLE_METRICS:
        value = metrics.get(key)
        metrics[key] = float(value) / months if value is not None else None

    metrics["costo_fijo_considerado_periodo"] = result.metricas.get(
        "costo_fijo_promedio_mensual"
    )
    metrics["punto_equilibrio_periodo"] = result.metricas.get(
        "punto_equilibrio_promedio_mensual"
    )
    metrics["gastos_fijos_estimados"] = result.metricas.get(
        "costo_fijo_promedio_mensual"
    )
    metrics["punto_equilibrio_ventas"] = result.metricas.get(
        "punto_equilibrio_promedio_mensual"
    )

    return replace(result, metricas=metrics)


def etiquetas_vista_pe(vista: str) -> dict[str, str]:
    if vista == VISTA_MENSUAL:
        return {
            "costo_fijo": "Costo fijo considerado mensual",
            "punto_equilibrio": "PE promedio mensual",
            "ventas": "Ventas promedio mensual",
            "holgura": "Holgura mensual sobre PE",
            "ventas_simuladas": "Ventas simuladas mensuales",
            "gastos_fijos_simulados": "Costo fijo simulado mensual",
            "ventas_requeridas": "Ventas requeridas mensuales",
            "holgura_simulada": "Holgura mensual",
            "resultado_simulado": "Resultado operacional mensual simulado",
        }
    if vista == VISTA_PERIODO:
        return {
            "costo_fijo": "Costo fijo considerado período",
            "punto_equilibrio": "PE período analizado",
            "ventas": "Ventas período",
            "holgura": "Holgura sobre PE período",
            "ventas_simuladas": "Ventas simuladas período",
            "gastos_fijos_simulados": "Costo fijo simulado período",
            "ventas_requeridas": "Ventas requeridas período",
            "holgura_simulada": "Holgura período",
            "resultado_simulado": "Resultado operacional simulado período",
        }
    raise ValueError(f"Vista de punto de equilibrio no soportada: {vista}")
