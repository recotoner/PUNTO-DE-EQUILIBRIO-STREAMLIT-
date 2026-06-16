"""Structural validation for normalized EERR and sales inputs."""

from __future__ import annotations

from src.config import EERR_REQUIRED_LABELS, VENTAS_REQUIRED_COLUMNS
from src.models import EERRNormalizado, ValidationResult, VentasNormalizadas


class InputValidator:
    @staticmethod
    def validate_eerr(eerr: EERRNormalizado) -> ValidationResult:
        result = ValidationResult()
        if not eerr.empresa:
            result.add_error("El EERR no informa la empresa.")
        if eerr.cuentas.empty:
            result.add_error("El EERR no contiene cuentas con valores.")

        missing = [label for label in EERR_REQUIRED_LABELS if label not in eerr.totales]
        if missing:
            result.add_error(
                "El EERR no contiene los totales obligatorios: " + ", ".join(missing)
            )

        if eerr.formato == "mensual":
            InputValidator._validate_monthly_totals(eerr, result)
        else:
            result.add_warning(
                "El EERR es acumulado; no se podran validar sumas ni tendencias mensuales."
            )
        return result

    @staticmethod
    def validate_ventas(ventas: VentasNormalizadas) -> ValidationResult:
        result = ValidationResult()
        missing = [
            column for column in VENTAS_REQUIRED_COLUMNS if column not in ventas.datos.columns
        ]
        if missing:
            result.add_error(
                "El archivo de ventas no contiene las columnas obligatorias: "
                + ", ".join(missing)
            )
            return result

        invalid_dates = int(ventas.datos["Fecha"].isna().sum())
        if invalid_dates:
            result.add_error(f"Ventas contiene {invalid_dates} filas con fecha invalida.")

        invalid_sales = int(ventas.datos["Total Linea"].isna().sum())
        if invalid_sales:
            result.add_error(
                f"Ventas contiene {invalid_sales} filas sin un valor numerico de venta."
            )

        result.metrics.update(
            {
                "ventas_filas_originales": ventas.filas_originales,
                "ventas_fecha_min": ventas.periodo_original.fecha_inicio.isoformat(),
                "ventas_fecha_max": ventas.periodo_original.fecha_fin.isoformat(),
            }
        )
        return result

    @staticmethod
    def _validate_monthly_totals(
        eerr: EERRNormalizado, result: ValidationResult
    ) -> None:
        inconsistent = []
        for row in eerr.cuentas.itertuples(index=False):
            monthly = row.valores_mensuales
            if not monthly:
                continue
            difference = abs(sum(monthly.values()) - row.total)
            if difference > 1:
                inconsistent.append(row.concepto)
        if inconsistent:
            result.add_error(
                f"El EERR contiene {len(inconsistent)} cuentas cuyo total no coincide "
                "con la suma mensual."
            )
