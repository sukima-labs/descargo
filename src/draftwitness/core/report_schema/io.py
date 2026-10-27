"""Reading, writing and publishing the report schema."""

from pathlib import Path
from typing import Any

from draftwitness.core.report_schema.models import Report


def load_report(path: Path) -> Report:
    """Load and validate a report JSON file."""
    return Report.model_validate_json(path.read_bytes())


def dump_report(report: Report) -> str:
    """Serialise a report as stable, human-readable JSON."""
    return report.model_dump_json(indent=2, exclude_none=True) + "\n"


def report_json_schema() -> dict[str, Any]:
    """The JSON Schema for the current report schema version."""
    return Report.model_json_schema(mode="validation")
