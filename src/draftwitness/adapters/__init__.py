"""Parsers that turn reports downloaded by the student into the common report schema."""

from draftwitness.adapters.base import AdapterError
from draftwitness.adapters.registry import REPORT_SUFFIXES, import_report

__all__ = ["REPORT_SUFFIXES", "AdapterError", "import_report"]
