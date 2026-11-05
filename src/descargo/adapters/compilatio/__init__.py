"""Compilatio analysis report downloaded as PDF (Magister and Magister+)."""

from descargo.adapters.compilatio.common import ADAPTER_NAME, ADAPTER_VERSION
from descargo.adapters.compilatio.pdf import detect_layout, parse_pdf

__all__ = ["ADAPTER_NAME", "ADAPTER_VERSION", "detect_layout", "parse_pdf"]
