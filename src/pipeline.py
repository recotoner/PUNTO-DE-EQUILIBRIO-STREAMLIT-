"""Application workflow independent from Streamlit."""

from __future__ import annotations

from dataclasses import replace

from src.adapters import VentasAdapter, cargar_eerr
from src.engine import (
    calcular_conciliacion_controller,
    calcular_punto_equilibrio_global,
    calcular_rentabilidad_comercial,
    calcular_resumen_global,
    detectar_nivel,
)
from src.models import NivelAnalisis, PipelineResult, ValidationResult
from src.validators import (
    ConciliationValidator,
    CostValidator,
    InputValidator,
    PeriodValidator,
)


def procesar_archivos(eerr_source, ventas_source=None) -> PipelineResult:
    validation = ValidationResult()
    try:
        eerr = cargar_eerr(eerr_source)
        validation.merge(InputValidator.validate_eerr(eerr))
        global_eerr = calcular_resumen_global(eerr)
        punto_equilibrio_global = calcular_punto_equilibrio_global(
            global_eerr,
            eerr,
        )
    except Exception as exc:
        validation.add_error(f"No fue posible procesar el EERR: {exc}")
        return PipelineResult(eerr=None, ventas=None, validation=validation, nivel=None)

    if ventas_source is None:
        nivel = detectar_nivel(
            eerr_valido=validation.valid,
            ventas_presentes=False,
            advertencias=tuple(validation.warnings),
        )
        return PipelineResult(
            eerr=eerr,
            ventas=None,
            validation=validation,
            nivel=nivel,
            global_eerr=global_eerr,
            punto_equilibrio_global=punto_equilibrio_global,
        )

    try:
        ventas = VentasAdapter().load(ventas_source)
        sales_input_validation = InputValidator.validate_ventas(ventas)
        validation.merge(sales_input_validation)

        ventas, period_validation = PeriodValidator.validate_and_filter(eerr, ventas)
        validation.merge(period_validation)

        cost_validation = CostValidator.validate(ventas)
        ventas = replace(
            ventas,
            datos_rentabilidad=cost_validation.metrics.get(
                "datos_rentabilidad_principal", ventas.datos.iloc[0:0].copy()
            ),
            datos_excluidos_costo=cost_validation.metrics.get(
                "datos_excluidos_costo_cero", ventas.datos.iloc[0:0].copy()
            ),
        )
        validation.merge(cost_validation)
        validation.merge(ConciliationValidator.validate(eerr, ventas))
    except Exception as exc:
        validation.add_error(f"No fue posible procesar ventas: {exc}")
        nivel = detectar_nivel(
            eerr_valido=True,
            ventas_presentes=True,
            ventas_validas=False,
            costos_disponibles=False,
            advertencias=tuple(validation.warnings + validation.errors),
        )
        return PipelineResult(
            eerr=eerr,
            ventas=None,
            validation=validation,
            nivel=nivel,
            global_eerr=global_eerr,
            punto_equilibrio_global=punto_equilibrio_global,
        )

    sales_valid = sales_input_validation.valid and period_validation.valid
    costs_available = bool(cost_validation.metrics.get("costos_disponibles", False))
    nivel = detectar_nivel(
        eerr_valido=True,
        ventas_presentes=True,
        ventas_validas=sales_valid,
        costos_disponibles=costs_available,
        advertencias=tuple(validation.warnings),
    )
    comercial = None
    conciliacion_controller = None
    if nivel is not None and nivel.nivel == NivelAnalisis.NIVEL_2_COMERCIAL:
        try:
            comercial = calcular_rentabilidad_comercial(ventas)
            conciliacion_controller = calcular_conciliacion_controller(
                global_eerr, comercial, validation.metrics
            )
        except Exception as exc:
            validation.add_error(
                f"No fue posible calcular la rentabilidad comercial: {exc}"
            )
            nivel = detectar_nivel(
                eerr_valido=True,
                ventas_presentes=True,
                ventas_validas=True,
                costos_disponibles=False,
                advertencias=tuple(validation.warnings + validation.errors),
            )

    return PipelineResult(
        eerr=eerr,
        ventas=ventas,
        validation=validation,
        nivel=nivel,
        global_eerr=global_eerr,
        punto_equilibrio_global=punto_equilibrio_global,
        comercial=comercial,
        conciliacion_controller=conciliacion_controller,
    )
