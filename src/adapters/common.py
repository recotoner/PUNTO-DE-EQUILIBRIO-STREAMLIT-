"""Helpers shared by spreadsheet adapters."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import BinaryIO, TypeAlias

ExcelSource: TypeAlias = str | Path | BinaryIO


def normalizar_texto(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def clave_texto(value: object) -> str:
    return normalizar_texto(value).upper()
