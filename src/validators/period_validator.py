"""Period consistency rules and sales filtering."""

from __future__ import annotations

from dataclasses import replace

from src.models import EERRNormalizado, ValidationResult, VentasNormalizadas


class PeriodValidator:
    @staticmethod
    def validate_and_filter(
        eerr: EERRNormalizado, ventas: VentasNormalizadas
    ) -> tuple[VentasNormalizadas, ValidationResult]:
        result = ValidationResult()
        dates = ventas.datos["Fecha"]
        mask = (
            dates.notna()
            & (dates.dt.date >= eerr.periodo.fecha_inicio)
            & (dates.dt.date <= eerr.periodo.fecha_fin)
        )
        filtered_data = ventas.datos.loc[mask].copy()
        excluded = int((~mask).sum())

        filtered = replace(
            ventas,
            datos=filtered_data,
            periodo_analizado=eerr.periodo,
            filas_analizadas=len(filtered_data),
            filas_fuera_periodo=excluded,
        )
        result.metrics.update(
            {
                "periodo_eerr": eerr.periodo.etiqueta,
                "ventas_filas_analizadas": len(filtered_data),
                "ventas_filas_fuera_periodo": excluded,
            }
        )

        if excluded:
            result.add_warning(
                f"Se excluyeron {excluded} filas de ventas fuera del periodo del EERR."
            )
        if filtered_data.empty:
            result.add_error(
                "Ventas no contiene filas dentro del periodo informado por el EERR."
            )
        return filtered, result
