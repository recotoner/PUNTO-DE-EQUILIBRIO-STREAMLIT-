"""Streamlit presentation layer for the layered V1 workflow."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit_echarts import st_echarts
import requests

from src.config import N8N_PE_WEBHOOK_URL
from src.engine import calcular_sensibilidad_pe
from src.integrations import enviar_payload_n8n
from src.models import NivelAnalisis
from src.pipeline import procesar_archivos
from src.reports import (
    VISTA_MENSUAL,
    VISTA_PERIODO,
    construir_payload_agente,
    construir_nombre_pdf,
    construir_grafico_pe_global,
    construir_vista_pe,
    etiquetas_vista_pe,
    generar_pdf_ejecutivo,
)
from src.theme import aplicar_tema_kappo, renderizar_hero


def format_currency(value) -> str:
    if value is None:
        return "No disponible"
    return f"${value:,.0f}".replace(",", ".")


def format_percent(value) -> str:
    if value is None:
        return "No disponible"
    return f"{value:.1%}".replace(".", ",")


COMMERCIAL_TABLE_FORMAT = {
    "Cantidad vendida valida": "{:,.2f}",
    "Venta neta valida": format_currency,
    "Costo total valido": format_currency,
    "Margen $": format_currency,
    "Margen %": format_percent,
    "Participacion venta valida": format_percent,
    "Participacion margen": format_percent,
    "Lineas excluidas mismo SKU": "{:,.0f}",
    "Venta excluida mismo SKU": format_currency,
}

CONTROLLER_TABLE_FORMAT = {
    "EERR": format_currency,
    "Comercial valido": format_currency,
    "Detalle total": format_currency,
    "Diferencia": format_currency,
    "Diferencia % EERR": format_percent,
    "Diferencia %": format_percent,
}

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo-kappo.png"


st.set_page_config(
    page_title="Punto de Equilibrio y Rentabilidad",
    page_icon="",
    layout="wide",
)
aplicar_tema_kappo()

with st.sidebar:
    st.image(str(LOGO_PATH), width="stretch")
    st.markdown("---")
    st.header("Fuente de datos")
    eerr_file = st.file_uploader(
        "Estado de resultados (obligatorio)",
        type=["xlsx"],
        help="Se aceptan formatos mensuales y acumulados.",
    )
    sales_file = st.file_uploader(
        "Detalle de ventas (opcional)",
        type=["xlsx"],
    )
    process = st.button(
        "Procesar archivos",
        type="primary",
        width="stretch",
        disabled=eerr_file is None,
    )
    st.caption("Kappo Consultores · Versión interna V1")

if process:
    with st.spinner("Normalizando y validando archivos..."):
        st.session_state["pipeline_result"] = procesar_archivos(
            eerr_file, sales_file
        )

result = st.session_state.get("pipeline_result")
if result is not None and result.eerr is not None:
    renderizar_hero(
        logo_path=LOGO_PATH,
        empresa=result.eerr.empresa,
        periodo=result.eerr.periodo.etiqueta,
        formato=result.eerr.formato,
    )
else:
    renderizar_hero(logo_path=LOGO_PATH)

if result is None:
    st.info("Carga el EERR y, opcionalmente, el detalle de ventas para iniciar.")
    st.stop()

if result.eerr is None or result.global_eerr is None:
    st.error("El EERR no pudo normalizarse para generar el analisis global.")
    for error in result.validation.errors:
        st.error(error)
    st.stop()

# Layer 1: mandatory global EERR analysis.
global_panel = st.container(border=True)
global_panel.header("1. Análisis global EERR")
global_panel.caption(
    f"{result.eerr.empresa} | Periodo {result.eerr.periodo.etiqueta} | "
    f"Formato {result.eerr.formato}"
)
global_metrics = result.global_eerr.metricas

sales_col, cost_col, margin_col, margin_pct_col = global_panel.columns(4)
sales_col.metric("Ventas EERR", format_currency(global_metrics["ventas_eerr"]))
cost_col.metric(
    "Costo de ventas EERR",
    format_currency(global_metrics["costo_ventas_eerr"]),
)
margin_col.metric("Margen EERR", format_currency(global_metrics["margen_eerr"]))
margin_pct_col.metric(
    "Margen EERR %",
    format_percent(global_metrics["margen_eerr_pct"]),
)

admin_col, operating_col, profit_col = global_panel.columns(3)
admin_col.metric(
    "Gastos administración y ventas",
    format_currency(global_metrics["gastos_administracion_ventas"]),
)
operating_col.metric(
    "Resultado operacional",
    format_currency(global_metrics["resultado_operacional"]),
)
profit_col.metric(
    "Utilidad / pérdida",
    format_currency(global_metrics["utilidad_perdida"]),
)

# Layer 2: validation status and enabled level.
validation_panel = st.container(border=True)
validation_panel.header("2. Validaciones y nivel habilitado")
validation_panel.caption(
    "Control de calidad de archivos, cobertura de costos y nivel de análisis disponible."
)

metrics = result.validation.metrics
coverage_value = (
    metrics.get("cobertura_costo_valido")
    if result.ventas is not None
    else None
)

if result.nivel is None:
    validation_panel.error("El EERR no superó las validaciones obligatorias.")
else:
    visible_level = (
        "Nivel 2 · Análisis comercial habilitado"
        if result.nivel.nivel == NivelAnalisis.NIVEL_2_COMERCIAL
        else result.nivel.nivel.value
    )
    validation_panel.metric("Nivel habilitado", visible_level)
    if result.nivel.nivel == NivelAnalisis.NIVEL_2_COMERCIAL:
        validation_panel.info(
            "EERR y ventas permiten análisis comercial. Existen advertencias de "
            "calidad de datos que deben revisarse antes de interpretar resultados "
            "finales."
        )
    elif result.nivel.razones:
        validation_panel.info(result.nivel.razones[0])

load_format_col, load_period_col, rows_col, coverage_col = (
    validation_panel.columns(4)
)
load_format_col.metric("Formato EERR", result.eerr.formato.title())
load_period_col.metric("Período EERR", result.eerr.periodo.etiqueta)
rows_col.metric(
    "Filas de ventas analizadas",
    result.ventas.filas_analizadas if result.ventas else "Sin ventas",
)
coverage_col.metric(
    "Cobertura de costo válido",
    format_percent(coverage_value),
)

if result.ventas is not None:
    required_cost_metrics = {
        "venta_total_analizada",
        "venta_con_costo_valido",
        "venta_excluida_costo_cero",
        "lineas_excluidas_costo_cero",
        "cobertura_costo_valido",
    }
    if (
        metrics.get("cost_validation_schema") != 2
        or not required_cost_metrics.issubset(metrics)
    ):
        validation_panel.error(
            "El servidor conserva una version anterior del validador de costos. "
            "Reinicie Streamlit y vuelva a procesar los archivos."
        )
        st.stop()

with validation_panel.expander(
    "Ver controles de calidad y advertencias",
    expanded=False,
):
    if result.validation.errors:
        st.markdown("#### Errores")
        for error in result.validation.errors:
            st.error(error)

    if result.validation.warnings:
        st.markdown("#### Advertencias")
        for warning in result.validation.warnings:
            st.warning(warning)

    if result.ventas is None:
        st.info("No se cargó detalle de ventas para controles adicionales.")
    else:
        excluded_period_col, zero_cost_col, cost_gap_col = st.columns(3)
        excluded_period_col.metric(
            "Filas fuera del período",
            result.ventas.filas_fuera_periodo,
        )
        zero_cost_col.metric(
            "Líneas con costo cero",
            metrics["lineas_excluidas_costo_cero"],
        )
        cost_gap_col.metric(
            "Diferencia de costos",
            format_percent(metrics.get("conciliacion_costos_diferencia_pct")),
        )

        st.markdown("#### Control de cobertura de costos")
        total_col, valid_col, excluded_col = st.columns(3)
        total_col.metric(
            "Venta total analizada",
            format_currency(metrics["venta_total_analizada"]),
        )
        valid_col.metric(
            "Venta con costo válido",
            format_currency(metrics["venta_con_costo_valido"]),
        )
        excluded_col.metric(
            "Venta excluida por costo cero",
            format_currency(metrics["venta_excluida_costo_cero"]),
        )

        excluded_rows_col, detailed_coverage_col = st.columns(2)
        excluded_rows_col.metric(
            "Líneas excluidas por costo cero",
            metrics["lineas_excluidas_costo_cero"],
        )
        detailed_coverage_col.metric(
            "Cobertura de costo válido",
            format_percent(metrics["cobertura_costo_valido"]),
        )

        classification_summary = metrics.get(
            "costos_cero_resumen_clasificacion"
        )
        if (
            classification_summary is not None
            and not classification_summary.empty
        ):
            st.markdown("#### Resumen de líneas excluidas")
            st.dataframe(
                classification_summary.style.format(
                    {"Filas": "{:,.0f}", "Venta asociada": format_currency}
                ),
                width="stretch",
                hide_index=True,
            )

        zero_cost_summary = metrics.get("costos_cero_resumen")
        if zero_cost_summary is not None and not zero_cost_summary.empty:
            st.markdown("#### Productos, servicios y ajustes excluidos")
            st.dataframe(
                zero_cost_summary.style.format(
                    {"Filas": "{:,.0f}", "Venta asociada": format_currency}
                ),
                width="stretch",
                hide_index=True,
            )

with validation_panel.expander("Ver detalle normalizado del EERR"):
    st.dataframe(
        result.eerr.cuentas.drop(columns=["valores_mensuales"], errors="ignore"),
        width="stretch",
        hide_index=True,
    )

# Layer 3: optional commercial profitability.
commercial_panel = st.container(border=True)
commercial_panel.header("3. Rentabilidad comercial - Nivel 2")
commercial_panel.caption(
    "Lectura comercial calculada exclusivamente sobre líneas con costo válido informado."
)
if (
    result.nivel is None
    or result.nivel.nivel != NivelAnalisis.NIVEL_2_COMERCIAL
    or result.comercial is None
):
    commercial_panel.info(
        "La rentabilidad comercial se muestra solo cuando Nivel 2 está habilitado."
    )
else:
    comercial = result.comercial
    commercial_metrics = comercial.metricas

    commercial_sales_col, commercial_cost_col, commercial_margin_col, commercial_pct_col = (
        commercial_panel.columns(4)
    )
    commercial_sales_col.metric(
        "Venta neta valida",
        format_currency(commercial_metrics["venta_neta_valida"]),
    )
    commercial_cost_col.metric(
        "Costo total valido",
        format_currency(commercial_metrics["costo_total_valido"]),
    )
    commercial_margin_col.metric(
        "Margen comercial",
        format_currency(commercial_metrics["margen_comercial"]),
    )
    commercial_pct_col.metric(
        "Margen comercial %",
        format_percent(commercial_metrics["margen_comercial_pct"]),
    )

    valid_lines_col, excluded_lines_col, excluded_sales_col = (
        commercial_panel.columns(3)
    )
    valid_lines_col.metric(
        "Lineas validas",
        commercial_metrics["cantidad_lineas_validas"],
    )
    excluded_lines_col.metric(
        "Lineas excluidas",
        commercial_metrics["cantidad_lineas_excluidas"],
    )
    excluded_sales_col.metric(
        "Venta excluida por costo cero",
        format_currency(commercial_metrics["venta_excluida_costo_cero"]),
    )

    with commercial_panel.expander("Top 10 por margen", expanded=True):
        st.dataframe(
            comercial.top_margen.style.format(COMMERCIAL_TABLE_FORMAT),
            width="stretch",
            hide_index=True,
        )

    with commercial_panel.expander("Bottom 10 por margen %"):
        st.dataframe(
            comercial.bottom_margen_pct.style.format(COMMERCIAL_TABLE_FORMAT),
            width="stretch",
            hide_index=True,
        )

    with commercial_panel.expander(
        "Productos con venta relevante y margen bajo"
    ):
        st.caption(
            "Criterio V1: participación en venta válida desde 1% y margen % "
            "inferior al margen comercial global."
        )
        if comercial.venta_relevante_margen_bajo.empty:
            st.info("No se detectaron productos bajo el criterio configurado.")
        else:
            st.dataframe(
                comercial.venta_relevante_margen_bajo.style.format(
                    COMMERCIAL_TABLE_FORMAT
                ),
                width="stretch",
                hide_index=True,
            )

    with commercial_panel.expander(
        "Ver rentabilidad completa por SKU / producto"
    ):
        st.dataframe(
            comercial.rentabilidad_por_producto.style.format(
                COMMERCIAL_TABLE_FORMAT
            ),
            width="stretch",
            hide_index=True,
        )

# Layer 4: controller bridge between accounting and commercial views.
controller_panel = st.container(border=True)
controller_panel.header("4. Conciliación controller")
controller_panel.caption(
    "Puente de control entre la lectura contable del EERR y la base comercial válida."
)
if result.conciliacion_controller is None:
    controller_panel.info(
        "La conciliación entre margen EERR y margen comercial válido estará "
        "disponible cuando Nivel 2 esté habilitado."
    )
else:
    controller = result.conciliacion_controller
    controller_metrics = controller.metricas
    eerr_margin_col, commercial_margin_col, difference_col = (
        controller_panel.columns(3)
    )
    eerr_margin_col.metric(
        "Margen EERR",
        format_currency(controller_metrics["margen_eerr"]),
    )
    commercial_margin_col.metric(
        "Margen comercial válido",
        format_currency(controller_metrics["margen_comercial_valido"]),
    )
    difference_col.metric(
        "Diferencia de margen",
        format_currency(controller_metrics["diferencia_margen"]),
        delta=format_percent(controller_metrics["diferencia_margen_pct_eerr"]),
    )

    controller_panel.markdown("#### Lectura controller")
    controller_panel.info(controller.interpretacion)

    controller_panel.markdown("#### Comparación EERR vs base comercial válida")
    controller_panel.dataframe(
        controller.comparacion.style.format(CONTROLLER_TABLE_FORMAT),
        width="stretch",
        hide_index=True,
    )

    with controller_panel.expander("Ver conciliación EERR vs detalle total"):
        st.dataframe(
            controller.conciliacion_fuentes.style.format(CONTROLLER_TABLE_FORMAT),
            width="stretch",
            hide_index=True,
        )

    for observation in controller.observaciones:
        controller_panel.caption(observation)

# Layer 5: operational break-even approximation based only on EERR.
pe_panel = st.container(border=True)
pe_panel.header("5. Punto de equilibrio global")
pe_panel.caption(
    "Este punto de equilibrio es una aproximación operacional basada en el EERR. "
    "Considera costo de ventas como costo variable aproximado y estima los costos "
    "fijos desde cuentas operativas del período. No reemplaza un análisis de costos "
    "detallado por producto, canal o centro de costo."
)

if result.punto_equilibrio_global is None:
    pe_panel.warning(
        "No fue posible preparar el cálculo de punto de equilibrio global."
    )
    pe_view_result = None
    pe_view_labels = None
    pe_view = VISTA_MENSUAL
else:
    pe_global = result.punto_equilibrio_global
    pe_view_key = pe_panel.radio(
        "Vista de punto de equilibrio",
        options=["mensual", "periodo"],
        index=0,
        horizontal=True,
        format_func=lambda option: {
            "mensual": VISTA_MENSUAL,
            "periodo": VISTA_PERIODO,
        }[option],
        key="vista_punto_equilibrio",
    )
    pe_view = VISTA_MENSUAL if pe_view_key == "mensual" else VISTA_PERIODO
    pe_view_result = construir_vista_pe(pe_global, pe_view)
    pe_view_labels = etiquetas_vista_pe(pe_view)
    pe_metrics = pe_view_result.metricas
    months = int(pe_global.metricas.get("cantidad_meses_periodo") or 1)
    pe_panel.caption(f"Período analizado: {months} meses")

    fixed_cost_col, break_even_col, current_sales_col = pe_panel.columns(3)
    fixed_cost_col.metric(
        pe_view_labels["costo_fijo"],
        format_currency(pe_metrics["gastos_fijos_estimados"]),
    )
    break_even_col.metric(
        pe_view_labels["punto_equilibrio"],
        format_currency(pe_metrics["punto_equilibrio_ventas"]),
    )
    current_sales_col.metric(
        pe_view_labels["ventas"],
        format_currency(pe_metrics["ventas_eerr"]),
    )

    buffer_col, contribution_col = pe_panel.columns(2)
    buffer_col.metric(
        pe_view_labels["holgura"],
        format_currency(pe_metrics["holgura_sobre_pe"]),
        delta=format_percent(pe_metrics["holgura_sobre_pe_pct"]),
    )
    contribution_col.metric(
        "Margen contribución",
        format_percent(pe_metrics["margen_contribucion_pct_aproximado"]),
    )

    if not pe_global.composicion_costo_fijo.empty:
        with pe_panel.expander("Composición del costo fijo considerado"):
            fixed_cost_composition = pe_global.composicion_costo_fijo.copy()
            fixed_cost_composition["Promedio mensual"] = (
                fixed_cost_composition["Monto del período"] / months
            )
            st.dataframe(
                fixed_cost_composition.style.format(
                    {
                        "Monto del período": format_currency,
                        "Promedio mensual": format_currency,
                    }
                ),
                width="stretch",
                hide_index=True,
            )

    for warning in pe_global.advertencias:
        pe_panel.warning(warning)

    if pe_global.calculable:
        chart = construir_grafico_pe_global(pe_view_result, vista=pe_view)
        with pe_panel:
            st_echarts(
                options=chart["options"],
                height="520px",
                width="100%",
                key="pe_global_operacional",
            )

# Layer 6: hypothetical sensitivity scenarios.
sensitivity_panel = st.container(border=True)
sensitivity_panel.header("6. Sensibilidad del punto de equilibrio")
sensitivity_panel.caption(
    "Los controles siguientes representan escenarios hipotéticos. No modifican "
    "los datos reales del EERR ni los cálculos base de las secciones anteriores."
)

sensitivity = None
sales_variation = 0
variable_cost_variation = 0
fixed_cost_variation = 0
target_profit = 0

if (
    pe_view_result is None
    or not pe_view_result.calculable
):
    sensitivity_panel.warning(
        "La sensibilidad requiere un punto de equilibrio global base calculable."
    )
else:
    sales_variation_col, variable_cost_variation_col, fixed_cost_variation_col = (
        sensitivity_panel.columns(3)
    )
    sales_variation = sales_variation_col.slider(
        "Variación ventas %",
        min_value=-90,
        max_value=300,
        value=0,
        step=5,
        key="sensibilidad_ventas_pct",
    )
    variable_cost_variation = variable_cost_variation_col.slider(
        "Variación costo variable proporcional %",
        min_value=-80,
        max_value=200,
        value=0,
        step=5,
        key="sensibilidad_costo_variable_pct",
        help=(
            "Modifica el costo variable como proporción de las ventas simuladas."
        ),
    )
    fixed_cost_variation = fixed_cost_variation_col.slider(
        "Variación gastos fijos %",
        min_value=-80,
        max_value=200,
        value=0,
        step=5,
        key="sensibilidad_gastos_fijos_pct",
    )
    target_profit = sensitivity_panel.number_input(
        (
            "Utilidad operacional objetivo mensual ($)"
            if pe_view == VISTA_MENSUAL
            else "Utilidad operacional objetivo período ($)"
        ),
        value=0,
        step=1_000_000,
        format="%d",
        key="sensibilidad_utilidad_objetivo",
    )

    sensitivity = calcular_sensibilidad_pe(
        pe_view_result,
        variacion_ventas_pct=sales_variation / 100,
        variacion_costo_variable_pct=variable_cost_variation / 100,
        variacion_gastos_fijos_pct=fixed_cost_variation / 100,
        utilidad_operacional_objetivo=float(target_profit),
    )
    sensitivity_metrics = sensitivity.metricas

    simulated_sales_col, simulated_margin_col, simulated_fixed_col = (
        sensitivity_panel.columns(3)
    )
    simulated_sales_col.metric(
        pe_view_labels["ventas_simuladas"],
        format_currency(sensitivity_metrics["ventas_simuladas"]),
    )
    simulated_margin_col.metric(
        "Margen contribución simulado %",
        format_percent(
            sensitivity_metrics["margen_contribucion_pct_simulado"]
        ),
    )
    simulated_fixed_col.metric(
        pe_view_labels["gastos_fijos_simulados"],
        format_currency(sensitivity_metrics["gastos_fijos_simulados"]),
    )

    if sensitivity.calculable:
        target_pe_col, simulated_buffer_col, simulated_result_col = (
            sensitivity_panel.columns(3)
        )
        target_pe_col.metric(
            pe_view_labels["ventas_requeridas"],
            format_currency(sensitivity_metrics["punto_equilibrio_simulado"]),
        )
        simulated_buffer_col.metric(
            pe_view_labels["holgura_simulada"],
            format_currency(sensitivity_metrics["holgura_simulada"]),
            delta=format_percent(sensitivity_metrics["holgura_simulada_pct"]),
        )
        simulated_result_col.metric(
            pe_view_labels["resultado_simulado"],
            format_currency(
                sensitivity_metrics["resultado_operacional_simulado"]
            ),
        )

    for warning in sensitivity.advertencias:
        sensitivity_panel.warning(warning)

if result.ventas is not None:
    with validation_panel.expander("Ver muestra de ventas filtradas"):
        st.dataframe(
            result.ventas.datos.head(100),
            width="stretch",
            hide_index=True,
        )

agent_payload = construir_payload_agente(
    result,
    sensibilidad=sensitivity,
    vista_actual=pe_view,
    variacion_ventas_pct=float(sales_variation),
    variacion_costo_variable_pct=float(variable_cost_variation),
    variacion_gastos_fijos_pct=float(fixed_cost_variation),
    utilidad_objetivo=float(target_profit),
)
with st.expander("Ver payload para agente n8n", expanded=False):
    st.json(agent_payload)

st.subheader("Análisis ejecutivo automático")
if st.button(
    "Solicitar análisis automático",
    type="primary",
    key="enviar_payload_n8n",
):
    if N8N_PE_WEBHOOK_URL == "PEGAR_URL_AQUI":
        st.warning(
            "Configure la URL interna del webhook n8n antes de solicitar el análisis."
        )
    else:
        try:
            with st.spinner("Enviando payload al agente n8n..."):
                webhook_response = enviar_payload_n8n(
                    N8N_PE_WEBHOOK_URL,
                    agent_payload,
                    timeout=75,
                )
            st.session_state["n8n_agent_response"] = {
                "status_code": webhook_response.status_code,
                "texto": webhook_response.texto,
                "json_data": webhook_response.json_data,
            }
        except requests.exceptions.Timeout:
            st.error(
                "El agente n8n no respondió dentro del tiempo máximo configurado."
            )
        except requests.exceptions.RequestException as exc:
            st.error(f"No fue posible conectar con el webhook n8n: {exc}")

stored_agent_response = st.session_state.get("n8n_agent_response")
agent_json_response = (
    stored_agent_response.get("json_data")
    if isinstance(stored_agent_response, dict)
    else None
)
if isinstance(stored_agent_response, dict):
    st.markdown("### Informe ejecutivo Kappo")
    executive_report = None
    if isinstance(agent_json_response, dict):
        for report_key in (
            "resumen_ejecutivo",
            "informe_ejecutivo",
            "informe",
            "output",
            "respuesta",
        ):
            report_value = agent_json_response.get(report_key)
            if isinstance(report_value, str) and report_value.strip():
                executive_report = report_value.strip()
                break
    if executive_report is not None:
        st.markdown(executive_report)
    elif agent_json_response is None and stored_agent_response.get("texto"):
        st.markdown(stored_agent_response["texto"])
    else:
        st.info("El agente respondió correctamente. Revise la respuesta técnica.")

    with st.expander("Ver respuesta técnica del agente", expanded=False):
        st.write(f"Status HTTP: {stored_agent_response['status_code']}")
        st.markdown("**Respuesta cruda del webhook**")
        st.code(stored_agent_response.get("texto") or "(respuesta vacía)")
        if agent_json_response is not None:
            st.markdown("**Respuesta JSON**")
            st.json(agent_json_response)
else:
    st.warning("El PDF se generará sin análisis automático del agente.")

pdf_bytes = generar_pdf_ejecutivo(
    agent_payload,
    respuesta_agente=agent_json_response,
    logo_path=LOGO_PATH,
)
st.download_button(
    "Descargar informe ejecutivo PDF",
    data=pdf_bytes,
    file_name=construir_nombre_pdf(agent_payload),
    mime="application/pdf",
    width="stretch",
    key="descargar_informe_ejecutivo_pdf",
)
