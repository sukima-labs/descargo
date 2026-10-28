"""Compilatio analysis report downloaded as PDF (Magister and Magister+)."""

from draftwitness.adapters.compilatio.common import ADAPTER_NAME, ADAPTER_VERSION
from draftwitness.adapters.compilatio.pdf import detect_layout, parse_pdf

__all__ = ["ADAPTER_NAME", "ADAPTER_VERSION", "detect_layout", "parse_pdf"]
