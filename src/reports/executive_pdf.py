"""Executive Kappo PDF report built from the existing agent payload."""

from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

KAPPO_NAVY = colors.HexColor("#062657")
KAPPO_BLUE = colors.HexColor("#0B86D5")
KAPPO_LIGHT = colors.HexColor("#EAF5FB")
KAPPO_BORDER = colors.HexColor("#D8E3EC")
KAPPO_TEXT = colors.HexColor("#24364B")
KAPPO_MUTED = colors.HexColor("#65758A")
SCOPE_LIMITATION_TEXT = (
    "Este módulo no evalúa liquidez, pasivos, endeudamiento, capital de trabajo, "
    "flujo de caja ni capacidad de pago."
)


def generar_pdf_ejecutivo(
    payload: dict[str, Any],
    *,
    respuesta_agente: Any | None = None,
    logo_path: str | Path | None = None,
) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=16 * mm,
        title="Informe Ejecutivo de Punto de Equilibrio y Rentabilidad Comercial",
        author="Kappo Consultores",
    )
    styles = _styles()
    agent = _normalize_agent_response(respuesta_agente)
    story: list[Any] = []

    _add_cover(story, payload, logo_path, styles)
    story.append(PageBreak())
    _add_executive_summary(story, payload, agent, styles)
    _add_main_indicators(story, payload, styles)
    _add_break_even(story, payload, agent, styles)
    _add_sensitivity(story, payload, agent, styles)
    _add_commercial_profitability(story, payload, agent, styles)
    _add_reconciliation(story, payload, agent, styles)
    _add_alerts(story, payload, agent, styles)
    _add_agent_text_section(
        story,
        "8. Recomendaciones controller",
        agent.get("recomendaciones_controller"),
        (
            "Revisar las advertencias de calidad de datos y validar la composición "
            "del costo fijo antes de adoptar conclusiones definitivas."
        ),
        styles,
    )
    _add_conclusion(
        story,
        agent.get("conclusion"),
        _fallback_conclusion(payload),
        styles,
    )

    document.build(
        story,
        onFirstPage=_draw_page,
        onLaterPages=_draw_page,
    )
    return buffer.getvalue()


def construir_nombre_pdf(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata", {})
    company = _slug(metadata.get("nombre_empresa") or "empresa")
    start = metadata.get("periodo_inicio") or "inicio"
    end = metadata.get("periodo_fin") or "fin"
    return f"informe_pe_rentabilidad_kappo_{company}_{start}_{end}.pdf"


def _add_cover(
    story: list[Any],
    payload: dict[str, Any],
    logo_path: str | Path | None,
    styles: dict[str, ParagraphStyle],
) -> None:
    metadata = payload.get("metadata", {})
    if logo_path and Path(logo_path).exists():
        logo = Image(str(logo_path), width=72 * mm, height=22.8 * mm)
        logo.hAlign = "CENTER"
        story.extend([Spacer(1, 13 * mm), logo, Spacer(1, 14 * mm)])
    else:
        story.extend(
            [
                Spacer(1, 18 * mm),
                Paragraph("KAPPO CONSULTORES", styles["cover_brand"]),
                Spacer(1, 12 * mm),
            ]
        )

    story.append(
        Table(
            [[Paragraph("INFORME EJECUTIVO", styles["cover_eyebrow"])]],
            colWidths=[178 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), KAPPO_BLUE),
                    ("BOX", (0, 0), (-1, -1), 0, KAPPO_BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            ),
        )
    )
    story.extend(
        [
            Spacer(1, 7 * mm),
            Paragraph(
                "Punto de Equilibrio y<br/>Rentabilidad Comercial",
                styles["cover_title"],
            ),
            Spacer(1, 12 * mm),
        ]
    )
    cover_data = [
        ["Empresa", metadata.get("nombre_empresa") or "No informada"],
        [
            "Período",
            f"{metadata.get('periodo_inicio', '')} a {metadata.get('periodo_fin', '')}",
        ],
        ["Meses analizados", metadata.get("meses_periodo")],
        ["Fecha de generación", _format_generation_date(metadata.get("fecha_generacion"))],
        ["Clasificación", "Uso interno / informe gerencial Kappo"],
    ]
    story.append(_key_value_table(cover_data, styles, widths=[48 * mm, 130 * mm]))
    story.extend(
        [
            Spacer(1, 22 * mm),
            Paragraph(
                "Kappo Consultores · Consultoría y gestión a empresas",
                styles["cover_footer"],
            ),
        ]
    )


def _add_executive_summary(
    story: list[Any],
    payload: dict[str, Any],
    agent: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, "1. Resumen ejecutivo", styles)
    text = agent.get("resumen_ejecutivo") or _fallback_summary(payload)
    story.append(_paragraph(text, styles["body"]))
    story.append(_paragraph(SCOPE_LIMITATION_TEXT, styles["note"]))


def _add_main_indicators(
    story: list[Any],
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, "2. Indicadores principales", styles)
    pe = payload.get("punto_equilibrio", {})
    rows = [
        ["Ventas período", _clp(pe.get("ventas_periodo"))],
        ["Ventas promedio mensual", _clp(pe.get("ventas_mensual"))],
        ["Margen contribución", _pct(pe.get("margen_contribucion_pct"))],
        [
            "Costo fijo considerado período",
            _clp(pe.get("costo_fijo_considerado_periodo")),
        ],
        [
            "Costo fijo promedio mensual",
            _clp(pe.get("costo_fijo_considerado_mensual")),
        ],
        ["PE período", _clp(pe.get("pe_periodo"))],
        ["PE promedio mensual", _clp(pe.get("pe_mensual"))],
        ["Holgura período", _clp(pe.get("holgura_periodo"))],
        ["Holgura mensual", _clp(pe.get("holgura_mensual"))],
    ]
    story.append(_key_value_table(rows, styles))


def _add_break_even(
    story: list[Any],
    payload: dict[str, Any],
    agent: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, "3. Punto de equilibrio", styles)
    story.append(
        _paragraph(
            agent.get("lectura_punto_equilibrio")
            or _fallback_break_even(payload),
            styles["body"],
        )
    )
    composition = payload.get("punto_equilibrio", {}).get(
        "composicion_costo_fijo",
        [],
    )
    if composition:
        story.append(Spacer(1, 3 * mm))
        headers = [
            "Cuenta / subtotal",
            "Monto período",
            "Promedio mensual",
            "Criterio de inclusión",
        ]
        rows = [
            [
                item.get("cuenta_o_subtotal"),
                _clp(item.get("monto_periodo")),
                _clp(item.get("monto_mensual")),
                item.get("criterio_inclusion"),
            ]
            for item in composition
        ]
        story.append(
            _data_table(
                headers,
                rows,
                styles,
                widths=[45 * mm, 30 * mm, 30 * mm, 73 * mm],
                alignments=["LEFT", "RIGHT", "RIGHT", "LEFT"],
            )
        )


def _add_sensitivity(
    story: list[Any],
    payload: dict[str, Any],
    agent: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, "4. Sensibilidad", styles)
    story.append(
        _paragraph(
            agent.get("lectura_sensibilidad")
            or (
                "El escenario de sensibilidad corresponde a los supuestos vigentes "
                "al momento de generar este informe."
            ),
            styles["body"],
        )
    )
    sensitivity = payload.get("sensibilidad", {})
    rows = [
        ["Vista actual", _view_label(sensitivity.get("vista_actual"))],
        ["Variación ventas", _pct(sensitivity.get("variacion_ventas_pct"))],
        [
            "Variación costo variable proporcional",
            _pct(sensitivity.get("variacion_costo_variable_pct")),
        ],
        [
            "Variación gastos fijos",
            _pct(sensitivity.get("variacion_gastos_fijos_pct")),
        ],
        ["Utilidad objetivo", _clp(sensitivity.get("utilidad_objetivo"))],
        ["Ventas simuladas", _clp(sensitivity.get("ventas_simuladas"))],
        [
            "Margen contribución simulado",
            _pct(sensitivity.get("margen_contribucion_simulado_pct")),
        ],
        ["Costo fijo simulado", _clp(sensitivity.get("costo_fijo_simulado"))],
        ["Ventas requeridas", _clp(sensitivity.get("ventas_requeridas"))],
        ["Holgura simulada", _clp(sensitivity.get("holgura_simulada"))],
        [
            "Resultado operacional simulado",
            _clp(sensitivity.get("resultado_operacional_simulado")),
        ],
    ]
    story.append(_key_value_table(rows, styles))


def _add_commercial_profitability(
    story: list[Any],
    payload: dict[str, Any],
    agent: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, "5. Rentabilidad comercial", styles)
    commercial = payload.get("rentabilidad_comercial", {})
    story.append(
        _paragraph(
            agent.get("lectura_rentabilidad_comercial")
            or (
                "La rentabilidad comercial se calcula exclusivamente sobre líneas "
                "con costo válido informado."
            ),
            styles["body"],
        )
    )
    if not commercial.get("disponible"):
        story.append(
            Paragraph(
                "La rentabilidad comercial Nivel 2 no está disponible.",
                styles["note"],
            )
        )
        return

    summary_rows = [
        ["Venta neta válida", _clp(commercial.get("venta_neta_valida"))],
        ["Costo total válido", _clp(commercial.get("costo_total_valido"))],
        ["Margen comercial", _clp(commercial.get("margen_comercial"))],
        ["Margen comercial", _pct(commercial.get("margen_comercial_pct"))],
        ["Líneas válidas", _integer(commercial.get("lineas_validas"))],
        ["Líneas excluidas", _integer(commercial.get("lineas_excluidas"))],
        [
            "Cobertura costo válido",
            _pct(commercial.get("cobertura_costo_valido_pct")),
        ],
    ]
    story.append(_key_value_table(summary_rows, styles))

    products = commercial.get("top_productos_margen", [])[:5]
    if products:
        story.extend(
            [
                Spacer(1, 4 * mm),
                Paragraph("Top 5 productos por margen", styles["subheading"]),
            ]
        )
        headers = ["SKU", "Producto", "Venta neta", "Margen", "Margen %"]
        rows = [
            [
                item.get("sku"),
                item.get("producto"),
                _clp(item.get("venta_neta_valida")),
                _clp(item.get("margen")),
                _pct(item.get("margen_pct")),
            ]
            for item in products
        ]
        story.append(
            _data_table(
                headers,
                rows,
                styles,
                widths=[27 * mm, 71 * mm, 31 * mm, 31 * mm, 18 * mm],
                alignments=["LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"],
            )
        )


def _add_reconciliation(
    story: list[Any],
    payload: dict[str, Any],
    agent: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, "6. Conciliación controller", styles)
    reconciliation = payload.get("conciliacion", {})
    story.append(
        _paragraph(
            agent.get("lectura_conciliacion")
            or reconciliation.get("lectura_controller_actual")
            or "La conciliación controller no está disponible.",
            styles["body"],
        )
    )
    if reconciliation.get("ventas_eerr") is None:
        return
    headers = ["Concepto", "EERR", "Comercial válido", "Diferencia", "Diferencia %"]
    rows = [
        [
            "Ventas",
            _clp(reconciliation.get("ventas_eerr")),
            _clp(reconciliation.get("ventas_comercial_valido")),
            _clp(reconciliation.get("diferencia_ventas")),
            _pct(reconciliation.get("diferencia_ventas_pct")),
        ],
        [
            "Costo de ventas",
            _clp(reconciliation.get("costo_ventas_eerr")),
            _clp(reconciliation.get("costo_comercial_valido")),
            _clp(reconciliation.get("diferencia_costo")),
            _pct(reconciliation.get("diferencia_costo_pct")),
        ],
        [
            "Margen",
            _clp(reconciliation.get("margen_eerr")),
            _clp(reconciliation.get("margen_comercial_valido")),
            _clp(reconciliation.get("diferencia_margen")),
            _pct(reconciliation.get("diferencia_margen_pct")),
        ],
    ]
    story.append(
        _data_table(
            headers,
            rows,
            styles,
            widths=[34 * mm, 36 * mm, 39 * mm, 38 * mm, 31 * mm],
            alignments=["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
        )
    )


def _add_alerts(
    story: list[Any],
    payload: dict[str, Any],
    agent: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, "7. Alertas y limitaciones", styles)
    items = _as_text_list(agent.get("alertas_y_limitaciones"))
    warnings = payload.get("advertencias", {})
    items.extend(_as_text_list(warnings.get("lista")))
    items.extend(_as_text_list(warnings.get("notas_limitaciones")))
    items = _deduplicate_alerts(item for item in items if item)
    if not items:
        items = ["No se registraron alertas adicionales en el payload."]
    for item in items:
        story.append(Paragraph(f"• {_clean_text(item)}", styles["bullet"]))


def _add_agent_text_section(
    story: list[Any],
    title: str,
    value: Any,
    fallback: str,
    styles: dict[str, ParagraphStyle],
) -> None:
    _section_title(story, title, styles)
    items = _as_text_list(value)
    if not items:
        story.append(_paragraph(fallback, styles["body"]))
        return
    for item in items:
        story.append(Paragraph(f"• {_clean_text(item)}", styles["bullet"]))


def _add_conclusion(
    story: list[Any],
    value: Any,
    fallback: str,
    styles: dict[str, ParagraphStyle],
) -> None:
    items = _as_text_list(value) or [fallback]
    if not any(SCOPE_LIMITATION_TEXT in item for item in items):
        items.append(SCOPE_LIMITATION_TEXT)
    flowables: list[Any] = []
    _section_title(flowables, "9. Conclusión", styles)
    for item in items:
        flowables.append(Paragraph(f"• {_clean_text(item)}", styles["bullet"]))
    story.append(KeepTogether(flowables))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_brand": ParagraphStyle(
            "CoverBrand",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=KAPPO_NAVY,
            alignment=TA_CENTER,
        ),
        "cover_eyebrow": ParagraphStyle(
            "CoverEyebrow",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.white,
            leading=11,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=30,
            textColor=KAPPO_NAVY,
            alignment=TA_CENTER,
        ),
        "cover_footer": ParagraphStyle(
            "CoverFooter",
            parent=base["Normal"],
            fontSize=8.5,
            textColor=KAPPO_MUTED,
            alignment=TA_CENTER,
        ),
        "heading": ParagraphStyle(
            "Heading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=KAPPO_NAVY,
            spaceBefore=7 * mm,
            spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        "subheading": ParagraphStyle(
            "Subheading",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=KAPPO_NAVY,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13.2,
            textColor=KAPPO_TEXT,
            spaceAfter=3 * mm,
        ),
        "note": ParagraphStyle(
            "Note",
            parent=base["BodyText"],
            fontSize=8.7,
            leading=12,
            textColor=KAPPO_MUTED,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontSize=9,
            leading=12.5,
            leftIndent=4 * mm,
            firstLineIndent=-3 * mm,
            textColor=KAPPO_TEXT,
            spaceAfter=1.5 * mm,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
            textColor=KAPPO_TEXT,
        ),
        "table_cell_bold": ParagraphStyle(
            "TableCellBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=KAPPO_NAVY,
        ),
    }


def _key_value_table(
    rows: list[list[Any]],
    styles: dict[str, ParagraphStyle],
    widths: list[float] | None = None,
) -> Table:
    data = [
        [
            Paragraph(_clean_text(label), styles["table_cell_bold"]),
            Paragraph(_clean_text(value), styles["table_cell"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=widths or [82 * mm, 96 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), KAPPO_LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.45, KAPPO_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.1 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.1 * mm),
            ]
        )
    )
    return table


def _data_table(
    headers: list[str],
    rows: list[list[Any]],
    styles: dict[str, ParagraphStyle],
    *,
    widths: list[float],
    alignments: list[str],
) -> Table:
    data = [
        [Paragraph(_clean_text(item), styles["table_header"]) for item in headers]
    ]
    data.extend(
        [
            [Paragraph(_clean_text(item), styles["table_cell"]) for item in row]
            for row in rows
        ]
    )
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), KAPPO_NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, KAPPO_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, KAPPO_LIGHT]),
    ]
    for column, alignment in enumerate(alignments):
        commands.append(("ALIGN", (column, 1), (column, -1), alignment))
    table.setStyle(TableStyle(commands))
    return table


def _section_title(
    story: list[Any],
    title: str,
    styles: dict[str, ParagraphStyle],
) -> None:
    story.append(
        KeepTogether(
            [
                Paragraph(_clean_text(title), styles["heading"]),
                Table(
                    [[""]],
                    colWidths=[178 * mm],
                    rowHeights=[1.2 * mm],
                    style=TableStyle(
                        [("BACKGROUND", (0, 0), (-1, -1), KAPPO_BLUE)]
                    ),
                ),
                Spacer(1, 2.5 * mm),
            ]
        )
    )


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_clean_text(value), style)


def _draw_page(canvas, document) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(KAPPO_BORDER)
    canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
    canvas.setFillColor(KAPPO_MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(16 * mm, 7.5 * mm, "Kappo Consultores · Informe gerencial")
    canvas.drawRightString(
        width - 16 * mm,
        7.5 * mm,
        f"Página {document.page}",
    )
    canvas.restoreState()


def _normalize_agent_response(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, list):
        for item in value:
            normalized = _normalize_agent_response(item)
            if normalized:
                return normalized
        return {}
    if isinstance(value, str):
        try:
            return _normalize_agent_response(json.loads(value))
        except (json.JSONDecodeError, TypeError):
            return {"resumen_ejecutivo": value}
    if not isinstance(value, dict):
        return {}

    expected = {
        "resumen_ejecutivo",
        "lectura_punto_equilibrio",
        "lectura_sensibilidad",
        "lectura_rentabilidad_comercial",
        "lectura_conciliacion",
        "alertas_y_limitaciones",
        "recomendaciones_controller",
        "conclusion",
    }
    if expected.intersection(value):
        return value
    for key in ("output", "respuesta", "informe_ejecutivo", "data"):
        if key in value:
            normalized = _normalize_agent_response(value[key])
            if normalized:
                return normalized
    return value


def _fallback_summary(payload: dict[str, Any]) -> str:
    pe = payload.get("punto_equilibrio", {})
    return (
        f"Durante el período analizado, las ventas alcanzaron "
        f"{_clp(pe.get('ventas_periodo'))}, frente a un punto de equilibrio "
        f"estimado de {_clp(pe.get('pe_periodo'))}. La holgura del período es "
        f"{_clp(pe.get('holgura_periodo'))}. Estas cifras deben interpretarse "
        "considerando las advertencias y limitaciones incluidas en el informe."
    )


def _fallback_break_even(payload: dict[str, Any]) -> str:
    pe = payload.get("punto_equilibrio", {})
    return (
        f"El punto de equilibrio estimado es {_clp(pe.get('pe_mensual'))} "
        f"mensuales y {_clp(pe.get('pe_periodo'))} para el período acumulado, "
        f"con un margen de contribución de "
        f"{_pct(pe.get('margen_contribucion_pct'))}."
    )


def _fallback_conclusion(payload: dict[str, Any]) -> str:
    pe = payload.get("punto_equilibrio", {})
    buffer_value = pe.get("holgura_periodo")
    direction = (
        "por sobre" if isinstance(buffer_value, (int, float)) and buffer_value >= 0
        else "por debajo"
    )
    return (
        f"Las ventas del período se sitúan {direction} del punto de equilibrio "
        "estimado. Se recomienda validar la composición del costo fijo y las "
        "advertencias de calidad de datos antes de adoptar decisiones definitivas. "
        f"{SCOPE_LIMITATION_TEXT}"
    )


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items()]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _deduplicate_alerts(items: Any) -> list[str]:
    selected: dict[str, str] = {}
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = _alert_key(text)
        current = selected.get(key)
        if current is None or _clarity_score(text) > _clarity_score(current):
            selected[key] = text
    return list(selected.values())


def _alert_key(text: str) -> str:
    normalized = _normalize_for_key(text)
    if "fuera" in normalized and _has_period_word(normalized):
        return "filas_fuera_periodo"
    if "costo cero" in normalized or "lineas excluidas por costo" in normalized:
        return "costo_cero"
    if "costo fijo" in normalized and (
        "estimado" in normalized or "controller" in normalized
    ):
        return "costo_fijo_estimado"
    if "punto de equilibrio" in normalized and (
        "aproxim" in normalized
    ):
        return "pe_aproximado"
    if (
        "rentabilidad comercial" in normalized
        and "costo valido" in normalized
    ):
        return "rentabilidad_costo_valido"
    return normalized


def _has_period_word(normalized: str) -> bool:
    return (
        "periodo" in normalized
        or "period" in normalized
        or ("per" in normalized and "odo" in normalized)
    )


def _clarity_score(text: str) -> int:
    score = min(len(text), 240)
    normalized = _normalize_for_key(text)
    for term in ("revise", "controller", "antes de", "limitacion", "aproximacion"):
        if term in normalized:
            score += 35
    return score


def _normalize_for_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _clean_text(value: Any) -> str:
    if value is None:
        return "No disponible"
    text = str(value).strip()
    text = re.sub(r"#{1,6}\s*", "", text)
    text = text.replace("**", "").replace("__", "")
    text = escape(text).replace("\n", "<br/>")
    return text or "No disponible"


def _clp(value: Any) -> str:
    if value is None:
        return "No disponible"
    return f"${float(value):,.0f}".replace(",", ".")


def _pct(value: Any) -> str:
    if value is None:
        return "No disponible"
    return f"{float(value):.1f}%".replace(".", ",")


def _integer(value: Any) -> str:
    if value is None:
        return "No disponible"
    return f"{int(value):,}".replace(",", ".")


def _view_label(value: Any) -> str:
    return (
        "Promedio mensual"
        if value == "promedio_mensual"
        else "Período acumulado"
    )


def _format_generation_date(value: Any) -> str:
    if not value:
        return datetime.now().strftime("%d-%m-%Y %H:%M")
    try:
        return datetime.fromisoformat(str(value)).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return str(value)


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_").lower()
    return slug or "empresa"
