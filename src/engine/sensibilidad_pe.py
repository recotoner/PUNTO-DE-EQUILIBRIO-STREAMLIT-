"""Hypothetical sensitivity scenarios for the global break-even point."""

from __future__ import annotations

from src.models import PuntoEquilibrioGlobalResult, SensibilidadPEResult


def calcular_sensibilidad_pe(
    base: PuntoEquilibrioGlobalResult,
    *,
    variacion_ventas_pct: float = 0.0,
    variacion_costo_variable_pct: float = 0.0,
    variacion_gastos_fijos_pct: float = 0.0,
    utilidad_operacional_objetivo: float = 0.0,
) -> SensibilidadPEResult:
    metrics = base.metricas
    ventas_base = float(metrics.get("ventas_eerr") or 0)
    costo_variable_base = float(metrics.get("costo_ventas_eerr") or 0)
    gastos_fijos_base = float(metrics.get("gastos_fijos_estimados") or 0)

    ventas_simuladas = ventas_base * (1 + variacion_ventas_pct)
    ratio_costo_variable_base = (
        costo_variable_base / ventas_base if ventas_base > 0 else None
    )
    ratio_costo_variable_simulado = (
        ratio_costo_variable_base * (1 + variacion_costo_variable_pct)
        if ratio_costo_variable_base is not None
        else None
    )
    costo_variable_simulado = (
        ventas_simuladas * ratio_costo_variable_simulado
        if ratio_costo_variable_simulado is not None
        else 0.0
    )
    gastos_fijos_simulados = gastos_fijos_base * (1 + variacion_gastos_fijos_pct)
    margen_contribucion_pct_simulado = (
        1 - ratio_costo_variable_simulado
        if ratio_costo_variable_simulado is not None
        else None
    )

    result_metrics: dict[str, float | None] = {
        "ventas_simuladas": ventas_simuladas,
        "costo_variable_simulado": costo_variable_simulado,
        "ratio_costo_variable_simulado": ratio_costo_variable_simulado,
        "margen_contribucion_pct_simulado": margen_contribucion_pct_simulado,
        "gastos_fijos_simulados": gastos_fijos_simulados,
        "utilidad_operacional_objetivo": float(utilidad_operacional_objetivo),
        "punto_equilibrio_simulado": None,
        "holgura_simulada": None,
        "holgura_simulada_pct": None,
        "resultado_operacional_simulado": None,
    }
    warnings: list[str] = []

    if gastos_fijos_simulados < 0:
        warnings.append(
            "Los gastos fijos simulados son negativos. Se permite el escenario, "
            "pero corresponde a una situación no habitual."
        )
    if ventas_simuladas <= 0:
        warnings.append(
            "No es posible calcular el punto de equilibrio simulado porque las "
            "ventas simuladas son menores o iguales a cero."
        )
        return SensibilidadPEResult(
            calculable=False,
            metricas=result_metrics,
            advertencias=warnings,
        )
    if (
        margen_contribucion_pct_simulado is None
        or margen_contribucion_pct_simulado <= 0
    ):
        warnings.append(
            "No es posible calcular el punto de equilibrio simulado porque el "
            "margen de contribución simulado es menor o igual a cero."
        )
        return SensibilidadPEResult(
            calculable=False,
            metricas=result_metrics,
            advertencias=warnings,
        )

    required_sales = (
        gastos_fijos_simulados + utilidad_operacional_objetivo
    ) / margen_contribucion_pct_simulado
    simulated_buffer = ventas_simuladas - required_sales
    result_metrics.update(
        {
            "punto_equilibrio_simulado": required_sales,
            "holgura_simulada": simulated_buffer,
            "holgura_simulada_pct": simulated_buffer / ventas_simuladas,
            "resultado_operacional_simulado": (
                ventas_simuladas * margen_contribucion_pct_simulado
                - gastos_fijos_simulados
            ),
        }
    )
    if required_sales < 0:
        warnings.append(
            "El nivel de ventas requerido es negativo por los supuestos ingresados. "
            "Es un escenario matemáticamente válido, pero no habitual."
        )

    return SensibilidadPEResult(
        calculable=True,
        metricas=result_metrics,
        advertencias=warnings,
    )
