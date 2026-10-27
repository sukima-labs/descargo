"""Compilatio analysis report downloaded as PDF (Magister and Magister+)."""

from draftwitness.adapters.compilatio.pdf import (
    ADAPTER_NAME,
    ADAPTER_VERSION,
    detect_language,
    parse_pdf,
)

__all__ = ["ADAPTER_NAME", "ADAPTER_VERSION", "detect_language", "parse_pdf"]
