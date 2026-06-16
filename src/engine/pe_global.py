"""Global EERR summary calculations."""

from __future__ import annotations

import re

import pandas as pd

from src.models import (
    EERRNormalizado,
    GlobalEERRResult,
    PuntoEquilibrioGlobalResult,
)

FIXED_COST_COLUMNS = [
    "Cuenta o subtotal incluido",
    "Monto del período",
    "Criterio de inclusión",
]
FIXED_COST_SUBTOTALS = {
    "TOTAL GASTOS DE ADMINISTRACION Y VENTAS": (
        "Subtotal operativo de gastos de administración y ventas."
    ),
    "TOTAL SUELDOS Y LEYES SOCIALES": (
        "Subtotal de remuneraciones, leyes sociales y honorarios."
    ),
}
FIXED_COST_TERMS = (
    "SUELDOS",
    "REMUNERACIONES",
    "LEYES SOCIALES",
    "HONORARIOS",
    "ARRIENDO",
    "ARRENDAMIENTO",
    "SERVICIOS BASICOS",
    "GASTOS GENERALES",
    "SEGUROS",
    "PATENTES",
)
EXCLUDED_FIXED_COST_TERMS = (
    "COSTO DE VENTA",
    "COSTOS DE EXPLOTACION",
    "INGRESO",
    "DIFERENCIA DE CAMBIO",
    "GASTOS FINANCIEROS",
    "GASTOS BANCARIOS",
    "IMPUESTO",
    "RESULTADO",
)
FIXED_COST_ESTIMATION_WARNING = (
    "El costo fijo considerado fue estimado automáticamente desde cuentas del "
    "EERR. Debe ser revisado por el controller antes de usar el punto de "
    "equilibrio como valor definitivo."
)


def calcular_resumen_global(eerr: EERRNormalizado) -> GlobalEERRResult:
    ventas = _total(eerr, "TOTAL INGRESOS DE EXPLOTACION")
    costo = _total(eerr, "TOTAL COSTOS DE EXPLOTACION")
    margen = _total(eerr, "MARGEN DE EXPLOTACION")
    if margen is None and ventas is not None and costo is not None:
        margen = ventas - costo

    utilidad = _find_account_total(eerr, "UTILIDAD (PERDIDA) DEL EJERCICIO")
    return GlobalEERRResult(
        metricas={
            "ventas_eerr": ventas,
            "costo_ventas_eerr": costo,
            "margen_eerr": margen,
            "margen_eerr_pct": margen / ventas if ventas and margen is not None else None,
            "gastos_administracion_ventas": _total(
                eerr, "TOTAL GASTOS DE ADMINISTRACION Y VENTAS"
            ),
            "resultado_operacional": _total(eerr, "RESULTADO OPERACIONAL"),
            "utilidad_perdida": utilidad,
        }
    )


def calcular_punto_equilibrio_global(
    global_eerr: GlobalEERRResult,
    eerr: EERRNormalizado | None = None,
) -> PuntoEquilibrioGlobalResult:
    metrics = global_eerr.metricas
    ventas = _as_float(metrics.get("ventas_eerr"))
    costo_ventas = _as_float(metrics.get("costo_ventas_eerr"))
    composicion = _componer_costo_fijo(eerr, metrics)
    gastos_fijos = float(composicion["Monto del período"].sum())
    cantidad_meses = _cantidad_meses(eerr) if eerr is not None else 1
    gastos_fijos_mensuales = gastos_fijos / cantidad_meses
    margen = ventas - costo_ventas
    margin_rate = margen / ventas if ventas > 0 else None

    base_metrics: dict[str, float | None] = {
        "ventas_eerr": ventas,
        "costo_ventas_eerr": costo_ventas,
        "margen_eerr": margen,
        "margen_contribucion_pct_aproximado": margin_rate,
        "gastos_fijos_estimados": gastos_fijos,
        "costo_fijo_considerado_periodo": gastos_fijos,
        "costo_fijo_promedio_mensual": gastos_fijos_mensuales,
        "cantidad_meses_periodo": float(cantidad_meses),
        "punto_equilibrio_ventas": None,
        "punto_equilibrio_periodo": None,
        "punto_equilibrio_promedio_mensual": None,
        "holgura_sobre_pe": None,
        "holgura_sobre_pe_periodo": None,
        "holgura_sobre_pe_pct": None,
    }
    if ventas <= 0:
        return PuntoEquilibrioGlobalResult(
            calculable=False,
            metricas=base_metrics,
            advertencias=[
                "No es posible calcular el punto de equilibrio porque las ventas EERR "
                "son menores o iguales a cero.",
                FIXED_COST_ESTIMATION_WARNING,
            ],
            composicion_costo_fijo=composicion,
        )
    if margin_rate is None or margin_rate <= 0:
        return PuntoEquilibrioGlobalResult(
            calculable=False,
            metricas=base_metrics,
            advertencias=[
                "No es posible calcular el punto de equilibrio porque el margen de "
                "contribucion aproximado es menor o igual a cero.",
                FIXED_COST_ESTIMATION_WARNING,
            ],
            composicion_costo_fijo=composicion,
        )

    break_even_sales = gastos_fijos / margin_rate
    monthly_break_even_sales = gastos_fijos_mensuales / margin_rate
    buffer = ventas - break_even_sales
    base_metrics.update(
        {
            "punto_equilibrio_ventas": break_even_sales,
            "punto_equilibrio_periodo": break_even_sales,
            "punto_equilibrio_promedio_mensual": monthly_break_even_sales,
            "holgura_sobre_pe": buffer,
            "holgura_sobre_pe_periodo": buffer,
            "holgura_sobre_pe_pct": buffer / ventas,
        }
    )
    return PuntoEquilibrioGlobalResult(
        calculable=True,
        metricas=base_metrics,
        advertencias=[FIXED_COST_ESTIMATION_WARNING],
        composicion_costo_fijo=composicion,
    )


def _total(eerr: EERRNormalizado, key: str) -> float | None:
    value = eerr.totales.get(key)
    return float(value) if value is not None else None


def _find_account_total(eerr: EERRNormalizado, key: str) -> float | None:
    matches = eerr.cuentas.loc[eerr.cuentas["concepto_clave"].eq(key), "total"]
    return float(matches.iloc[0]) if not matches.empty else None


def _as_float(value: float | None) -> float:
    return float(value) if value is not None else 0.0


def _cantidad_meses(eerr: EERRNormalizado) -> int:
    inicio = eerr.periodo.fecha_inicio
    fin = eerr.periodo.fecha_fin
    return (fin.year - inicio.year) * 12 + fin.month - inicio.month + 1


def _componer_costo_fijo(
    eerr: EERRNormalizado | None,
    metrics: dict[str, float | None],
) -> pd.DataFrame:
    if eerr is None or eerr.cuentas.empty:
        return pd.DataFrame(
            [
                {
                    "Cuenta o subtotal incluido": (
                        "TOTAL GASTOS DE ADMINISTRACION Y VENTAS"
                    ),
                    "Monto del período": _as_float(
                        metrics.get("gastos_administracion_ventas")
                    ),
                    "Criterio de inclusión": FIXED_COST_SUBTOTALS[
                        "TOTAL GASTOS DE ADMINISTRACION Y VENTAS"
                    ],
                }
            ],
            columns=FIXED_COST_COLUMNS,
        )

    cuentas = eerr.cuentas.reset_index(drop=True)
    covered_rows: set[int] = set()
    included_rows: list[dict[str, float | str]] = []
    included_subtotal_keys: set[str] = set()

    for row_index, row in cuentas.iterrows():
        key = str(row["concepto_clave"])
        if key not in FIXED_COST_SUBTOTALS:
            continue
        included_subtotal_keys.add(key)
        included_rows.append(
            {
                "Cuenta o subtotal incluido": str(row["concepto"]),
                "Monto del período": float(row["total"]),
                "Criterio de inclusión": FIXED_COST_SUBTOTALS[key],
            }
        )
        covered_rows.update(_child_account_rows(cuentas, row_index))

    if (
        "TOTAL GASTOS DE ADMINISTRACION Y VENTAS"
        not in included_subtotal_keys
    ):
        included_rows.insert(
            0,
            {
                "Cuenta o subtotal incluido": (
                    "TOTAL GASTOS DE ADMINISTRACION Y VENTAS"
                ),
                "Monto del período": _as_float(
                    metrics.get("gastos_administracion_ventas")
                ),
                "Criterio de inclusión": FIXED_COST_SUBTOTALS[
                    "TOTAL GASTOS DE ADMINISTRACION Y VENTAS"
                ],
            },
        )

    for row_index, row in cuentas.iterrows():
        if row_index in covered_rows:
            continue
        key = str(row["concepto_clave"])
        if _is_structural_row(key) or _is_excluded_fixed_cost(key):
            continue
        matched_term = next((term for term in FIXED_COST_TERMS if term in key), None)
        if matched_term is None:
            continue
        included_rows.append(
            {
                "Cuenta o subtotal incluido": str(row["concepto"]),
                "Monto del período": float(row["total"]),
                "Criterio de inclusión": (
                    f"Cuenta identificada por criterio operativo: {matched_term.title()}."
                ),
            }
        )

    return pd.DataFrame(included_rows, columns=FIXED_COST_COLUMNS)


def _child_account_rows(cuentas: pd.DataFrame, subtotal_index: int) -> set[int]:
    children: set[int] = set()
    for row_index in range(subtotal_index - 1, -1, -1):
        key = str(cuentas.at[row_index, "concepto_clave"])
        if _is_structural_row(key):
            break
        children.add(row_index)
    return children


def _is_structural_row(key: str) -> bool:
    return bool(re.match(r"^(TOTAL |MARGEN |RESULTADO |UTILIDAD )", key))


def _is_excluded_fixed_cost(key: str) -> bool:
    return any(term in key for term in EXCLUDED_FIXED_COST_TERMS)
