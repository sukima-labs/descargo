"""Pick the adapter for a downloaded report and run it (ADR 004)."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from draftwitness.adapters import turnitin
from draftwitness.adapters.base import AdapterError
from draftwitness.core.report_schema import Report

REPORT_SUFFIXES: Final = (".json", ".pdf")


def import_report(path: Path, *, parsed_at: datetime) -> Report:
    """Read ``path``: a report already in DraftWitness JSON, or a downloaded report that an
    adapter recognises (for now, a Turnitin Similarity Report PDF). The file is only read."""
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            return Report.model_validate_json(data)
        except ValidationError as exc:
            raise AdapterError(f"not a valid DraftWitness report: {exc}") from exc
    if suffix == ".pdf":
        sha256 = hashlib.sha256(data).hexdigest()
        return turnitin.parse_pdf(data, path.name, sha256, parsed_at=parsed_at)
    raise AdapterError(f"unsupported report type {suffix!r}; use {' or '.join(REPORT_SUFFIXES)}")
