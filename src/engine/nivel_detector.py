"""Pure decision table for the enabled analysis level."""

from __future__ import annotations

from src.models import NivelAnalisis, NivelResult


def detectar_nivel(
    *,
    eerr_valido: bool,
    ventas_presentes: bool,
    ventas_validas: bool = False,
    costos_disponibles: bool = False,
    advertencias: tuple[str, ...] = (),
) -> NivelResult | None:
    if not eerr_valido:
        return None

    decision_table = {
        (False, False, False): NivelAnalisis.NIVEL_1_GLOBAL,
        (True, False, False): NivelAnalisis.NIVEL_1_GLOBAL_CON_ADVERTENCIA,
        (True, True, False): NivelAnalisis.NIVEL_1_GLOBAL_CON_ADVERTENCIA,
        (True, True, True): NivelAnalisis.NIVEL_2_COMERCIAL,
    }
    key = (ventas_presentes, ventas_validas, costos_disponibles)
    nivel = decision_table.get(key, NivelAnalisis.NIVEL_1_GLOBAL_CON_ADVERTENCIA)

    razones = {
        NivelAnalisis.NIVEL_1_GLOBAL: ["EERR valido y ventas no cargadas."],
        NivelAnalisis.NIVEL_1_GLOBAL_CON_ADVERTENCIA: [
            "El detalle de ventas no cumple los requisitos para habilitar Nivel 2."
        ],
        NivelAnalisis.NIVEL_2_COMERCIAL: [
            "EERR y ventas con costo validos para analisis comercial."
        ],
    }
    return NivelResult(
        nivel=nivel,
        razones=razones[nivel],
        advertencias=list(advertencias),
    )
