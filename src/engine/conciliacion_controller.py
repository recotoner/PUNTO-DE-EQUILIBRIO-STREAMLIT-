"""Controller reconciliation between global EERR and valid commercial detail."""

from __future__ import annotations

import pandas as pd

from src.config import (
    COST_RECONCILIATION_TOLERANCE,
    SALES_RECONCILIATION_TOLERANCE,
)
from src.models import (
    ConciliacionControllerResult,
    GlobalEERRResult,
    RentabilidadComercialResult,
)


def calcular_conciliacion_controller(
    global_eerr: GlobalEERRResult,
    comercial: RentabilidadComercialResult,
    validation_metrics: dict,
) -> ConciliacionControllerResult:
    global_metrics = global_eerr.metricas
    commercial_metrics = comercial.metricas

    ventas_eerr = float(global_metrics["ventas_eerr"] or 0)
    costos_eerr = float(global_metrics["costo_ventas_eerr"] or 0)
    margen_eerr = float(global_metrics["margen_eerr"] or 0)
    ventas_comerciales = float(commercial_metrics["venta_neta_valida"])
    costos_comerciales = float(commercial_metrics["costo_total_valido"])
    margen_comercial = float(commercial_metrics["margen_comercial"])

    comparison = pd.DataFrame(
        [
            _row("Ventas", ventas_eerr, ventas_comerciales),
            _row("Costo de ventas", costos_eerr, costos_comerciales),
            _row("Margen", margen_eerr, margen_comercial),
        ]
    )
    source_reconciliation = pd.DataFrame(
        [
            {
                "Concepto": "Ventas",
                "EERR": validation_metrics.get("conciliacion_ventas_eerr"),
                "Detalle total": validation_metrics.get(
                    "conciliacion_ventas_detalle"
                ),
                "Diferencia": validation_metrics.get(
                    "conciliacion_ventas_diferencia"
                ),
                "Diferencia %": validation_metrics.get(
                    "conciliacion_ventas_diferencia_pct"
                ),
            },
            {
                "Concepto": "Costo de ventas",
                "EERR": validation_metrics.get("conciliacion_costos_eerr"),
                "Detalle total": validation_metrics.get(
                    "conciliacion_costos_detalle"
                ),
                "Diferencia": validation_metrics.get(
                    "conciliacion_costos_diferencia"
                ),
                "Diferencia %": validation_metrics.get(
                    "conciliacion_costos_diferencia_pct"
                ),
            },
        ]
    )
    margin_difference = margen_comercial - margen_eerr
    sales_difference_rate = float(
        validation_metrics.get("conciliacion_ventas_diferencia_pct") or 0
    )
    cost_difference_rate = abs(costos_comerciales - costos_eerr) / abs(costos_eerr) if costos_eerr else 0.0
    cost_coverage = float(validation_metrics.get("cobertura_costo_valido") or 0)
    excluded_lines = int(validation_metrics.get("lineas_excluidas_costo_cero") or 0)
    excluded_sales = float(validation_metrics.get("venta_excluida_costo_cero") or 0)
    interpretation = interpretar_conciliacion_controller(
        diferencia_ventas_pct=sales_difference_rate,
        diferencia_costos_pct=cost_difference_rate,
        diferencia_margen=margin_difference,
        cobertura_costo_valido=cost_coverage,
        lineas_excluidas_costo_cero=excluded_lines,
        venta_excluida_costo_cero=excluded_sales,
    )
    observations = [
        f"Cobertura de costo válido sobre ventas: {cost_coverage:.1%}.",
        f"Líneas excluidas por costo cero: {excluded_lines}.",
    ]

    return ConciliacionControllerResult(
        metricas={
            "margen_eerr": margen_eerr,
            "margen_comercial_valido": margen_comercial,
            "diferencia_margen": margin_difference,
            "diferencia_margen_pct_eerr": (
                abs(margin_difference) / abs(margen_eerr) if margen_eerr else 0.0
            ),
            "diferencia_ventas_pct": sales_difference_rate,
            "diferencia_costos_pct": cost_difference_rate,
            "cobertura_costo_valido": cost_coverage,
            "lineas_excluidas_costo_cero": excluded_lines,
            "venta_excluida_costo_cero": excluded_sales,
        },
        comparacion=comparison,
        conciliacion_fuentes=source_reconciliation,
        interpretacion=interpretation,
        observaciones=observations,
    )


def _row(concept: str, eerr: float, commercial: float) -> dict[str, float | str]:
    difference = commercial - eerr
    return {
        "Concepto": concept,
        "EERR": eerr,
        "Comercial valido": commercial,
        "Diferencia": difference,
        "Diferencia % EERR": abs(difference) / abs(eerr) if eerr else 0.0,
    }


def interpretar_conciliacion_controller(
    *,
    diferencia_ventas_pct: float,
    diferencia_costos_pct: float,
    diferencia_margen: float,
    cobertura_costo_valido: float,
    lineas_excluidas_costo_cero: int,
    venta_excluida_costo_cero: float,
) -> str:
    """Build a generic controller reading using only available V1 evidence."""
    sales_reconcile = diferencia_ventas_pct <= SALES_RECONCILIATION_TOLERANCE
    cost_is_material = diferencia_costos_pct > COST_RECONCILIATION_TOLERANCE

    opening = (
        "El margen comercial se calcula únicamente sobre líneas de venta con costo "
        "válido informado. El margen EERR corresponde al registro contable global "
        "del período."
    )
    sales_text = (
        " Las ventas del detalle concilian razonablemente con el EERR."
        if sales_reconcile
        else " Las ventas del detalle presentan una diferencia material frente al EERR."
    )

    if cost_is_material:
        cost_text = (
            " Existe una brecha material entre el costo de ventas contable y el costo "
            "explicado por la base comercial válida. Esta brecha no debe interpretarse "
            "automáticamente como error ni atribuirse a una causa única: podría estar "
            "relacionada con diferencias de valorización, timing contable, movimientos "
            "de inventario, ajustes, costos no reflejados en el detalle comercial, "
            "productos o servicios con costo cero, notas de crédito o diferencias de "
            "reconocimiento."
        )
        recommendation = (
            " Se recomienda revisar la composición del costo de ventas contable antes "
            "de usar el margen comercial como margen contable definitivo."
        )
    else:
        cost_text = (
            " El margen comercial válido es consistente con la base de ventas disponible "
            "y no presenta diferencias materiales relevantes contra el costo contable "
            "del EERR."
        )
        recommendation = (
            " Aun así, debe interpretarse como margen comercial calculado sobre líneas "
            "con costo informado, no como reemplazo automático del margen contable."
        )

    quality_text = (
        f" La cobertura de costo válido es {cobertura_costo_valido:.1%}; "
        f"se excluyeron {lineas_excluidas_costo_cero} líneas por costo cero"
        f", asociadas a ventas por {venta_excluida_costo_cero:,.0f}."
    )
    margin_text = (
        f" La diferencia entre ambos márgenes es {diferencia_margen:,.0f}."
    )
    return (
        opening
        + sales_text
        + cost_text
        + quality_text
        + margin_text
        + recommendation
    )
