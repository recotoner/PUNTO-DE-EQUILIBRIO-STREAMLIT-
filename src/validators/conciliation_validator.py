"""Reconciliation between EERR totals and filtered commercial detail."""

from __future__ import annotations

from src.config import (
    COST_RECONCILIATION_TOLERANCE,
    SALES_RECONCILIATION_TOLERANCE,
)
from src.models import EERRNormalizado, ValidationResult, VentasNormalizadas


class ConciliationValidator:
    @staticmethod
    def validate(
        eerr: EERRNormalizado, ventas: VentasNormalizadas
    ) -> ValidationResult:
        result = ValidationResult()
        if "Total Linea" not in ventas.datos.columns:
            return result

        eerr_sales = float(eerr.totales.get("TOTAL INGRESOS DE EXPLOTACION", 0))
        eerr_cost = float(eerr.totales.get("TOTAL COSTOS DE EXPLOTACION", 0))
        detail_sales = float(ventas.datos["Total Linea"].fillna(0).sum())
        detail_cost = (
            float(ventas.datos["Costo Venta Total"].fillna(0).sum())
            if "Costo Venta Total" in ventas.datos.columns
            else None
        )

        sales_rate = ConciliationValidator._difference_rate(detail_sales, eerr_sales)
        cost_rate = (
            ConciliationValidator._difference_rate(detail_cost, eerr_cost)
            if detail_cost is not None
            else None
        )
        result.metrics.update(
            {
                "conciliacion_ventas_eerr": eerr_sales,
                "conciliacion_ventas_detalle": detail_sales,
                "conciliacion_ventas_diferencia": detail_sales - eerr_sales,
                "conciliacion_ventas_diferencia_pct": sales_rate,
                "conciliacion_costos_eerr": eerr_cost,
                "conciliacion_costos_detalle": detail_cost,
                "conciliacion_costos_diferencia": (
                    detail_cost - eerr_cost if detail_cost is not None else None
                ),
                "conciliacion_costos_diferencia_pct": cost_rate,
            }
        )

        if sales_rate > SALES_RECONCILIATION_TOLERANCE:
            result.add_warning(
                f"La diferencia de ventas es material ({sales_rate:.1%}); "
                f"el umbral es {SALES_RECONCILIATION_TOLERANCE:.1%}."
            )
        if cost_rate is not None and cost_rate > COST_RECONCILIATION_TOLERANCE:
            result.add_warning(
                f"La diferencia de costos es material ({cost_rate:.1%}); "
                f"el umbral es {COST_RECONCILIATION_TOLERANCE:.1%}."
            )
        return result

    @staticmethod
    def _difference_rate(detail: float, reference: float) -> float:
        if reference == 0:
            return 0.0 if detail == 0 else 1.0
        return abs(detail - reference) / abs(reference)
