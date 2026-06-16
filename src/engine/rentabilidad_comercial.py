"""Basic commercial profitability calculations for Level 2."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import RELEVANT_PRODUCT_SALES_SHARE
from src.models import RentabilidadComercialResult, VentasNormalizadas


def obtener_base_rentabilidad(ventas: VentasNormalizadas) -> pd.DataFrame:
    """Return only rows with valid line-level costs informed by the source file."""
    return ventas.datos_rentabilidad.copy()


def calcular_rentabilidad_comercial(
    ventas: VentasNormalizadas,
) -> RentabilidadComercialResult:
    validas = obtener_base_rentabilidad(ventas)
    excluidas = ventas.datos_excluidos_costo.copy()
    if validas.empty:
        raise ValueError("No existen lineas con costo valido para calcular rentabilidad.")

    venta_neta = float(validas["Total Linea"].sum())
    costo_total = float(validas["Costo Venta Total"].sum())
    margen = venta_neta - costo_total
    margen_pct = margen / venta_neta if venta_neta else 0.0
    venta_excluida = (
        float(excluidas["Total Linea"].fillna(0).sum()) if not excluidas.empty else 0.0
    )

    tabla = _agrupar_rentabilidad(validas, excluidas, venta_neta, margen)
    positivos = tabla.loc[tabla["Venta neta valida"] > 0].copy()

    top_margen = tabla.nlargest(10, "Margen $").reset_index(drop=True)
    bottom_margen_pct = (
        positivos.nsmallest(10, "Margen %").reset_index(drop=True)
        if not positivos.empty
        else tabla.iloc[0:0].copy()
    )
    venta_relevante_margen_bajo = (
        positivos.loc[
            (positivos["Participacion venta valida"] >= RELEVANT_PRODUCT_SALES_SHARE)
            & (positivos["Margen %"] < margen_pct)
        ]
        .sort_values(
            ["Participacion venta valida", "Margen %"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )

    return RentabilidadComercialResult(
        metricas={
            "venta_neta_valida": venta_neta,
            "costo_total_valido": costo_total,
            "margen_comercial": margen,
            "margen_comercial_pct": margen_pct,
            "cantidad_lineas_validas": len(validas),
            "cantidad_lineas_excluidas": len(excluidas),
            "venta_excluida_costo_cero": venta_excluida,
        },
        rentabilidad_por_producto=tabla,
        top_margen=top_margen,
        bottom_margen_pct=bottom_margen_pct,
        venta_relevante_margen_bajo=venta_relevante_margen_bajo,
    )


def _agrupar_rentabilidad(
    validas: pd.DataFrame,
    excluidas: pd.DataFrame,
    venta_total_valida: float,
    margen_total: float,
) -> pd.DataFrame:
    working = _with_product_key(validas)
    grouped = (
        working.groupby(
            ["_clave_producto", "SKU", "Producto"],
            dropna=False,
            as_index=False,
        )
        .agg(
            **{
                "Cantidad vendida valida": ("Cantidad", "sum"),
                "Venta neta valida": ("Total Linea", "sum"),
                "Costo total valido": ("Costo Venta Total", "sum"),
            }
        )
    )
    grouped["Margen $"] = (
        grouped["Venta neta valida"] - grouped["Costo total valido"]
    )
    grouped["Margen %"] = np.where(
        grouped["Venta neta valida"].ne(0),
        grouped["Margen $"] / grouped["Venta neta valida"],
        np.nan,
    )
    grouped["Participacion venta valida"] = (
        grouped["Venta neta valida"] / venta_total_valida if venta_total_valida else 0.0
    )
    grouped["Participacion margen"] = (
        grouped["Margen $"] / margen_total if margen_total else 0.0
    )

    excluded_summary = _agrupar_excluidas(excluidas)
    grouped = grouped.merge(excluded_summary, on="_clave_producto", how="left")
    grouped["Lineas excluidas mismo SKU"] = (
        grouped["Lineas excluidas mismo SKU"].fillna(0).astype(int)
    )
    grouped["Venta excluida mismo SKU"] = grouped[
        "Venta excluida mismo SKU"
    ].fillna(0.0)

    return (
        grouped.drop(columns="_clave_producto")
        .sort_values("Margen $", ascending=False)
        .reset_index(drop=True)
    )


def _agrupar_excluidas(excluidas: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "_clave_producto",
        "Lineas excluidas mismo SKU",
        "Venta excluida mismo SKU",
    ]
    if excluidas.empty:
        return pd.DataFrame(columns=columns)

    working = _with_product_key(excluidas)
    return (
        working.groupby("_clave_producto", as_index=False)
        .agg(
            **{
                "Lineas excluidas mismo SKU": ("_clave_producto", "size"),
                "Venta excluida mismo SKU": ("Total Linea", "sum"),
            }
        )
    )


def _with_product_key(data: pd.DataFrame) -> pd.DataFrame:
    working = data.copy()
    sku = working["SKU"].fillna("").astype(str).str.strip()
    product = working["Producto"].fillna("Producto no informado").astype(str).str.strip()
    working["SKU"] = sku.mask(sku.eq(""), "Sin SKU")
    working["Producto"] = product.mask(product.eq(""), "Producto no informado")
    working["_clave_producto"] = np.where(
        working["SKU"].ne("Sin SKU"),
        "SKU:" + working["SKU"],
        "PRODUCTO:" + working["Producto"],
    )
    return working
