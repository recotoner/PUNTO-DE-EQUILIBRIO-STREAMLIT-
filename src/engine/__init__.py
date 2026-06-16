"""Analysis engines."""

from .conciliacion_controller import calcular_conciliacion_controller
from .nivel_detector import detectar_nivel
from .pe_global import calcular_punto_equilibrio_global, calcular_resumen_global
from .rentabilidad_comercial import calcular_rentabilidad_comercial
from .sensibilidad_pe import calcular_sensibilidad_pe

__all__ = [
    "calcular_conciliacion_controller",
    "calcular_punto_equilibrio_global",
    "calcular_rentabilidad_comercial",
    "calcular_resumen_global",
    "calcular_sensibilidad_pe",
    "detectar_nivel",
]
