"""Adapter for detailed sales spreadsheets."""

from __future__ import annotations

import pandas as pd

from src.adapters.common import ExcelSource, clave_texto
from src.models import Periodo, VentasNormalizadas

CANONICAL_COLUMNS = {
    "FECHA": "Fecha",
    "TOTAL LINEA": "Total Linea",
    "COSTO VENTA UNITARIO": "Costo Venta Unitario",
    "COSTO VENTA TOTAL": "Costo Venta Total",
    "CANTIDAD": "Cantidad",
    "DOCUMENTO": "Documento",
    "TIPO DOCUMENTO": "Documento",
    "SKU": "SKU",
    "PRODUCTO": "Producto",
    "GLOSA": "Glosa",
    "DESCRIPCION": "Descripcion",
    "DESCRIPCION PRODUCTO": "Descripcion",
    "VENDEDOR": "Vendedor",
    "FAMILIA": "Familia",
}


class VentasAdapter:
    def load(self, source: ExcelSource) -> VentasNormalizadas:
        data = pd.read_excel(source, sheet_name=0, engine="openpyxl")
        data = data.dropna(how="all").copy()
        data.columns = [
            CANONICAL_COLUMNS.get(clave_texto(column), str(column).strip())
            for column in data.columns
        ]
        if "Fecha" not in data.columns:
            raise ValueError("El archivo de ventas no contiene la columna Fecha.")

        data["Fecha"] = pd.to_datetime(data["Fecha"], dayfirst=True, errors="coerce")
        valid_dates = data["Fecha"].dropna()
        if valid_dates.empty:
            raise ValueError("El archivo de ventas no contiene fechas validas.")

        for column in ("Total Linea", "Costo Venta Unitario", "Costo Venta Total", "Cantidad"):
            if column in data.columns:
                data[column] = pd.to_numeric(data[column], errors="coerce")

        periodo = Periodo(valid_dates.min().date(), valid_dates.max().date())
        cost_columns = {"Costo Venta Unitario", "Costo Venta Total"}
        return VentasNormalizadas(
            datos=data,
            periodo_original=periodo,
            periodo_analizado=None,
            filas_originales=len(data),
            filas_analizadas=len(data),
            filas_fuera_periodo=0,
            tiene_columnas_costo=cost_columns.issubset(data.columns),
        )
