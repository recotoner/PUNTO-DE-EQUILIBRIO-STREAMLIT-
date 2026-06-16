"""Cost availability and zero-cost coverage validation."""

from __future__ import annotations

import pandas as pd

from src.adapters.common import clave_texto
from src.config import (
    MIN_NON_ZERO_COST_COVERAGE,
    VENTAS_COST_COLUMNS,
    ZERO_COST_ADJUSTMENT_KEYWORDS,
    ZERO_COST_SERVICE_KEYWORDS,
)
from src.models import ValidationResult, VentasNormalizadas

ZERO_COST_WARNING = (
    "Se detectaron líneas con costo cero. Algunas pueden corresponder a servicios, "
    "despachos o ítems no inventariables. Revise el detalle antes de interpretar "
    "rentabilidad comercial. Estas líneas fueron excluidas del cálculo principal."
)

ZERO_COST_CLASS_SERVICE = (
    "Posible servicio / despacho / recargo / ítem no inventariable"
)
ZERO_COST_CLASS_REVIEW = "Producto con costo cero que requiere revisión"
ZERO_COST_CLASS_ADJUSTMENT = "Nota de crédito o ajuste legítimo"


class CostValidator:
    @staticmethod
    def validate(ventas: VentasNormalizadas) -> ValidationResult:
        result = ValidationResult()
        missing = [
            column for column in VENTAS_COST_COLUMNS if column not in ventas.datos.columns
        ]
        if missing:
            result.add_error(
                "Ventas no contiene las columnas de costo requeridas: " + ", ".join(missing)
            )
            result.metrics["costos_disponibles"] = False
            return result

        null_mask = ventas.datos[list(VENTAS_COST_COLUMNS)].isna().any(axis=1)
        null_count = int(null_mask.sum())
        if null_count:
            result.add_error(
                f"Ventas contiene {null_count} filas con costo unitario o total nulo."
            )

        zero_mask = ventas.datos["Costo Venta Total"].eq(0) | ventas.datos[
            "Costo Venta Unitario"
        ].eq(0)
        zero_count = int(zero_mask.sum())
        total_rows = len(ventas.datos)
        valid_cost_mask = ~zero_mask & ~null_mask
        valid_cost_rows = ventas.datos.loc[valid_cost_mask].copy()
        zero_detail = CostValidator._classify_zero_cost_rows(
            ventas.datos.loc[zero_mask].copy()
        )
        zero_summary = CostValidator._summarize_zero_cost_rows(zero_detail)
        zero_classification_summary = (
            CostValidator._summarize_zero_cost_classifications(zero_detail)
        )
        total_sales = float(ventas.datos["Total Linea"].fillna(0).sum())
        valid_cost_sales = float(valid_cost_rows["Total Linea"].fillna(0).sum())
        zero_sales = float(zero_detail["Total Linea"].fillna(0).sum())
        row_coverage = (
            float(valid_cost_mask.sum() / total_rows) if total_rows else 0.0
        )
        sales_coverage = (
            valid_cost_sales / total_sales
            if total_sales
            else (1.0 if valid_cost_rows.empty else 0.0)
        )
        costs_available = (
            null_count == 0 and row_coverage >= MIN_NON_ZERO_COST_COVERAGE
        )
        result.metrics.update(
            {
                "cost_validation_schema": 2,
                "costos_disponibles": costs_available,
                "venta_total_analizada": total_sales,
                "venta_con_costo_valido": valid_cost_sales,
                "venta_excluida_costo_cero": zero_sales,
                "lineas_con_costo_valido": int(valid_cost_mask.sum()),
                "lineas_excluidas_costo_cero": zero_count,
                "cobertura_costo_valido": sales_coverage,
                "cobertura_costo_valido_filas": row_coverage,
                "datos_rentabilidad_principal": valid_cost_rows,
                "datos_excluidos_costo_cero": zero_detail,
                # Backward-compatible metric names used by the current dashboard.
                "cobertura_costo_no_cero": row_coverage,
                "costos_cero_filas": zero_count,
                "costos_cero_porcentaje_filas": zero_count / total_rows if total_rows else 0,
                "costos_cero_venta_neta": zero_sales,
                "costos_cero_detalle": zero_detail,
                "costos_cero_resumen": zero_summary,
                "costos_cero_resumen_clasificacion": zero_classification_summary,
            }
        )
        if zero_count:
            result.add_warning(ZERO_COST_WARNING)
        if null_count == 0 and not costs_available:
            result.add_error(
                "La cobertura de costos distintos de cero es insuficiente para habilitar "
                f"Nivel 2 ({row_coverage:.1%}; minimo "
                f"{MIN_NON_ZERO_COST_COVERAGE:.1%})."
            )
        return result

    @staticmethod
    def _classify_zero_cost_rows(data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            return data.assign(Clasificacion=pd.Series(dtype="object"))

        text_columns = [
            column
            for column in ("Producto", "SKU", "Documento", "Glosa", "Descripcion", "Familia")
            if column in data.columns
        ]

        def classify(row: pd.Series) -> str:
            document = clave_texto(row.get("Documento"))
            sale = row.get("Total Linea")
            if (
                any(keyword in document for keyword in ZERO_COST_ADJUSTMENT_KEYWORDS)
                or (pd.notna(sale) and float(sale) < 0)
            ):
                return ZERO_COST_CLASS_ADJUSTMENT

            searchable = " ".join(clave_texto(row.get(column)) for column in text_columns)
            if any(keyword in searchable for keyword in ZERO_COST_SERVICE_KEYWORDS):
                return ZERO_COST_CLASS_SERVICE
            return ZERO_COST_CLASS_REVIEW

        data["Clasificacion"] = data.apply(classify, axis=1)
        return data

    @staticmethod
    def _summarize_zero_cost_rows(data: pd.DataFrame) -> pd.DataFrame:
        columns = [
            "Clasificacion",
            "Producto",
            "SKU",
            "Filas",
            "Venta asociada",
        ]
        if data.empty:
            return pd.DataFrame(columns=columns)

        working = data.copy()
        for column in ("Producto", "SKU"):
            if column not in working.columns:
                working[column] = "No informado"
            working[column] = working[column].fillna("No informado").astype(str)

        return (
            working.groupby(
                ["Clasificacion", "Producto", "SKU"],
                dropna=False,
                as_index=False,
            )
            .agg(
                Filas=("Clasificacion", "size"),
                **{"Venta asociada": ("Total Linea", "sum")},
            )
            .sort_values(
                ["Clasificacion", "Venta asociada"],
                ascending=[True, False],
            )
            .reset_index(drop=True)
        )

    @staticmethod
    def _summarize_zero_cost_classifications(data: pd.DataFrame) -> pd.DataFrame:
        columns = ["Clasificacion", "Filas", "Venta asociada"]
        if data.empty:
            return pd.DataFrame(columns=columns)

        return (
            data.groupby("Clasificacion", as_index=False)
            .agg(
                Filas=("Clasificacion", "size"),
                **{"Venta asociada": ("Total Linea", "sum")},
            )
            .sort_values("Clasificacion")
            .reset_index(drop=True)
        )
