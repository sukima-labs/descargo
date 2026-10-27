"""Common intermediate report format shared by adapters and modules (see ADR 004)."""

from draftwitness.core.report_schema.io import dump_report, load_report, report_json_schema
from draftwitness.core.report_schema.models import (
    SCHEMA_VERSION,
    AiSegment,
    AiWriting,
    Match,
    Provenance,
    Report,
    ReportFile,
    ReportKind,
    Similarity,
    SimilarityFilters,
    Source,
    SourceKind,
    Submission,
    Tool,
)

__all__ = [
    "SCHEMA_VERSION",
    "AiSegment",
    "AiWriting",
    "Match",
    "Provenance",
    "Report",
    "ReportFile",
    "ReportKind",
    "Similarity",
    "SimilarityFilters",
    "Source",
    "SourceKind",
    "Submission",
    "Tool",
    "dump_report",
    "load_report",
    "report_json_schema",
]
