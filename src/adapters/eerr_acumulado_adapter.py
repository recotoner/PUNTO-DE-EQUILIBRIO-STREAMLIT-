"""Adapter for accumulated EERR files with only a total column."""

from src.adapters.eerr_base import EERRBaseAdapter


class EERRAcumuladoAdapter(EERRBaseAdapter):
    formato = "acumulado"
