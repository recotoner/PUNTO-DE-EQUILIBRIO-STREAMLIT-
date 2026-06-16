"""Normalized domain models shared by adapters, validators and engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd


class NivelAnalisis(StrEnum):
    NIVEL_1_GLOBAL = "NIVEL_1_GLOBAL"
    NIVEL_1_GLOBAL_CON_ADVERTENCIA = "NIVEL_1_GLOBAL_CON_ADVERTENCIA"
    NIVEL_2_COMERCIAL = "NIVEL_2_COMERCIAL"


@dataclass(frozen=True)
class Periodo:
    fecha_inicio: date
    fecha_fin: date

    def __post_init__(self) -> None:
        if self.fecha_inicio > self.fecha_fin:
            raise ValueError("La fecha de inicio no puede ser posterior a la fecha final.")

    @property
    def etiqueta(self) -> str:
        return f"{self.fecha_inicio:%d-%m-%Y} a {self.fecha_fin:%d-%m-%Y}"

    def contiene(self, fecha: date) -> bool:
        return self.fecha_inicio <= fecha <= self.fecha_fin


@dataclass
class EERRNormalizado:
    empresa: str
    rut: str
    periodo: Periodo
    formato: str
    cuentas: pd.DataFrame
    totales: dict[str, float]
    meses: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VentasNormalizadas:
    datos: pd.DataFrame
    periodo_original: Periodo
    periodo_analizado: Periodo | None
    filas_originales: int
    filas_analizadas: int
    filas_fuera_periodo: int
    tiene_columnas_costo: bool
    datos_rentabilidad: pd.DataFrame = field(default_factory=pd.DataFrame)
    datos_excluidos_costo: pd.DataFrame = field(default_factory=pd.DataFrame)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        self.valid = self.valid and other.valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.metrics.update(other.metrics)
        return self


@dataclass
class NivelResult:
    nivel: NivelAnalisis
    razones: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


@dataclass
class RentabilidadComercialResult:
    metricas: dict[str, float | int]
    rentabilidad_por_producto: pd.DataFrame
    top_margen: pd.DataFrame
    bottom_margen_pct: pd.DataFrame
    venta_relevante_margen_bajo: pd.DataFrame


@dataclass
class GlobalEERRResult:
    metricas: dict[str, float | None]


@dataclass
class PuntoEquilibrioGlobalResult:
    calculable: bool
    metricas: dict[str, float | None]
    advertencias: list[str] = field(default_factory=list)
    composicion_costo_fijo: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class SensibilidadPEResult:
    calculable: bool
    metricas: dict[str, float | None]
    advertencias: list[str] = field(default_factory=list)


@dataclass
class ConciliacionControllerResult:
    metricas: dict[str, float]
    comparacion: pd.DataFrame
    conciliacion_fuentes: pd.DataFrame
    interpretacion: str
    observaciones: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    eerr: EERRNormalizado | None
    ventas: VentasNormalizadas | None
    validation: ValidationResult
    nivel: NivelResult | None
    global_eerr: GlobalEERRResult | None = None
    punto_equilibrio_global: PuntoEquilibrioGlobalResult | None = None
    comercial: RentabilidadComercialResult | None = None
    conciliacion_controller: ConciliacionControllerResult | None = None
