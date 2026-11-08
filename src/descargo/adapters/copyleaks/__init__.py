"""Copyleaks report downloaded as PDF (the 2022 and 2023 exports)."""

from descargo.adapters.copyleaks.pdf import ADAPTER_NAME, ADAPTER_VERSION, detect_layout, parse_pdf

__all__ = ["ADAPTER_NAME", "ADAPTER_VERSION", "detect_layout", "parse_pdf"]
