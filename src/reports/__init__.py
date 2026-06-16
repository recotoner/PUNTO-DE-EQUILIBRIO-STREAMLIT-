"""Report presentation helpers."""

from .agent_payload import construir_payload_agente
from .executive_pdf import construir_nombre_pdf, generar_pdf_ejecutivo
from .pe_global_chart import construir_grafico_pe_global
from .pe_view import (
    VISTA_MENSUAL,
    VISTA_PERIODO,
    construir_vista_pe,
    etiquetas_vista_pe,
)

__all__ = [
    "VISTA_MENSUAL",
    "VISTA_PERIODO",
    "construir_payload_agente",
    "construir_nombre_pdf",
    "generar_pdf_ejecutivo",
    "construir_grafico_pe_global",
    "construir_vista_pe",
    "etiquetas_vista_pe",
]
