"""Parsers that turn reports downloaded by the student into the common report schema."""

from descargo.adapters.base import AdapterError
from descargo.adapters.registry import REPORT_SUFFIXES, import_report

__all__ = ["REPORT_SUFFIXES", "AdapterError", "import_report"]
