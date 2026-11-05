"""Pre-submission inspector (ADR 006): report what a file contains, never change it."""

from descargo.modules.pre.inspect.engine import SUFFIXES, inspect_bytes, inspect_file
from descargo.modules.pre.inspect.models import (
    CodePoint,
    Finding,
    FindingKind,
    InspectedFile,
    Inspection,
    Level,
    Location,
    MetadataField,
    Occurrence,
)
from descargo.modules.pre.inspect.render import render_markdown

__all__ = [
    "SUFFIXES",
    "CodePoint",
    "Finding",
    "FindingKind",
    "InspectedFile",
    "Inspection",
    "Level",
    "Location",
    "MetadataField",
    "Occurrence",
    "inspect_bytes",
    "inspect_file",
    "render_markdown",
]
