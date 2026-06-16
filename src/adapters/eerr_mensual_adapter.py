"""Adapter for EERR files with one column per month."""

from src.adapters.eerr_base import EERRBaseAdapter


class EERRMensualAdapter(EERRBaseAdapter):
    formato = "mensual"
