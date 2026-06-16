"""ECharts option builder for the global operational break-even chart."""

from __future__ import annotations

from src.models import PuntoEquilibrioGlobalResult
from .pe_view import VISTA_MENSUAL, VISTA_PERIODO


def construir_grafico_pe_global(
    result: PuntoEquilibrioGlobalResult,
    points: int = 21,
    vista: str = VISTA_PERIODO,
) -> dict:
    if not result.calculable:
        raise ValueError("El punto de equilibrio no es calculable.")
    if points < 20:
        raise ValueError("El grafico requiere al menos 20 puntos.")

    metrics = result.metricas
    current_sales = float(metrics["ventas_eerr"] or 0)
    variable_cost = float(metrics["costo_ventas_eerr"] or 0)
    fixed_cost = float(metrics["gastos_fijos_estimados"] or 0)
    break_even_sales = float(metrics["punto_equilibrio_ventas"] or 0)
    if current_sales <= 0:
        raise ValueError("Las ventas EERR deben ser mayores a cero.")

    variable_cost_ratio = variable_cost / current_sales
    if vista == VISTA_MENSUAL:
        x_axis_name = "Ventas mensuales MM$"
        y_axis_name = "Montos mensuales MM$"
        current_sales_name = "Ventas promedio mensual"
        subtitle = "Cruce mensual entre ventas y costo total estimado según EERR."
    elif vista == VISTA_PERIODO:
        x_axis_name = "Ventas período MM$"
        y_axis_name = "Montos período MM$"
        current_sales_name = "Ventas período"
        subtitle = "Cruce del período entre ventas y costo total estimado según EERR."
    else:
        raise ValueError(f"Vista de punto de equilibrio no soportada: {vista}")

    max_sales = current_sales * 1.5
    step = max_sales / (points - 1)
    sales_points = [step * index for index in range(points)]
    sales_points.extend([break_even_sales, current_sales])
    sales_points = _sorted_unique(sales_points, tolerance=max_sales * 1e-9)

    scenarios = []
    for sales in sales_points:
        scenario_variable_cost = sales * variable_cost_ratio
        scenarios.append(
            {
                "ventas_escenario": sales,
                "costo_fijo": fixed_cost,
                "costo_variable": scenario_variable_cost,
                "costo_total": fixed_cost + scenario_variable_cost,
            }
        )

    scale = 1_000_000
    series_data = {
        "Ventas": [
            [row["ventas_escenario"] / scale, row["ventas_escenario"] / scale]
            for row in scenarios
        ],
        "Costo fijo": [
            [row["ventas_escenario"] / scale, row["costo_fijo"] / scale]
            for row in scenarios
        ],
        "Costo variable": [
            [row["ventas_escenario"] / scale, row["costo_variable"] / scale]
            for row in scenarios
        ],
        "Costo total": [
            [row["ventas_escenario"] / scale, row["costo_total"] / scale]
            for row in scenarios
        ],
    }

    options = {
        "title": {
            "text": "Punto de equilibrio operacional",
            "subtext": subtitle,
            "left": "center",
        },
        "tooltip": {
            "trigger": "axis",
        },
        "legend": {
            "data": list(series_data),
            "top": 48,
        },
        "grid": {
            "left": 75,
            "right": 45,
            "top": 95,
            "bottom": 65,
        },
        "xAxis": {
            "type": "value",
            "name": x_axis_name,
            "nameLocation": "middle",
            "nameGap": 38,
            "min": 0,
            "max": max_sales / scale,
        },
        "yAxis": {
            "type": "value",
            "name": y_axis_name,
            "nameLocation": "middle",
            "nameGap": 58,
            "min": 0,
        },
        "series": [
            _line_series("Ventas", series_data["Ventas"], "#2E86DE"),
            _line_series("Costo fijo", series_data["Costo fijo"], "#7F8C8D"),
            _line_series("Costo variable", series_data["Costo variable"], "#F39C12"),
            {
                **_line_series("Costo total", series_data["Costo total"], "#C0392B"),
                "markLine": {
                    "symbol": ["none", "none"],
                    "label": {
                        "formatter": f"PE: ${break_even_sales:,.0f}",
                    },
                    "lineStyle": {"type": "dashed", "color": "#8E44AD", "width": 2},
                    "data": [{"xAxis": break_even_sales / scale}],
                },
                "markPoint": {
                    "symbolSize": 58,
                    "data": [
                        {
                            "name": "Punto de equilibrio",
                            "coord": [
                                break_even_sales / scale,
                                break_even_sales / scale,
                            ],
                            "value": f"${break_even_sales:,.0f}",
                            "itemStyle": {"color": "#8E44AD"},
                        },
                        {
                            "name": current_sales_name,
                            "coord": [
                                current_sales / scale,
                                current_sales / scale,
                            ],
                            "value": f"${current_sales:,.0f}",
                            "itemStyle": {"color": "#27AE60"},
                        },
                    ],
                },
            },
        ],
    }
    return {
        "escenarios": scenarios,
        "options": options,
        "rango_max_ventas": max_sales,
        "ratio_costo_variable": variable_cost_ratio,
        "punto_equilibrio_ventas": break_even_sales,
    }


def _line_series(name: str, data: list[list[float]], color: str) -> dict:
    return {
        "name": name,
        "type": "line",
        "showSymbol": False,
        "smooth": False,
        "data": data,
        "lineStyle": {"width": 3, "color": color},
        "itemStyle": {"color": color},
    }


def _sorted_unique(values: list[float], tolerance: float) -> list[float]:
    unique: list[float] = []
    for value in sorted(values):
        if not unique or abs(value - unique[-1]) > tolerance:
            unique.append(value)
    return unique
