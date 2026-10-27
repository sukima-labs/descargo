"""Turnitin Similarity Report downloaded as PDF (Feedback Studio and enhanced layouts)."""

from draftwitness.adapters.base import AdapterError
from draftwitness.adapters.turnitin.pdf import (
    ADAPTER_NAME,
    ADAPTER_VERSION,
    detect_layout,
    parse_pdf,
)

__all__ = ["ADAPTER_NAME", "ADAPTER_VERSION", "AdapterError", "detect_layout", "parse_pdf"]
