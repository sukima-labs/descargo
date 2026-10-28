"""Pick the adapter for a downloaded report and run it (ADR 004)."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from draftwitness.adapters import compilatio, turnitin
from draftwitness.adapters.base import AdapterError
from draftwitness.adapters.pdftext import pdf_lines
from draftwitness.core.report_schema import Report
from draftwitness.i18n import t

REPORT_SUFFIXES: Final = (".json", ".pdf")


def import_report(path: Path, *, parsed_at: datetime) -> Report:
    """Read ``path``: a report already in DraftWitness JSON, or a downloaded report that an
    adapter recognises (a Turnitin Similarity Report or a Compilatio analysis report, as
    PDF). The file is only read."""
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            return Report.model_validate_json(data)
        except ValidationError as exc:
            raise AdapterError(f"not a valid DraftWitness report: {exc}") from exc
    if suffix == ".pdf":
        sha256 = hashlib.sha256(data).hexdigest()
        lines = pdf_lines(data)
        if compilatio.detect_layout(lines) is not None:
            return compilatio.parse_pdf(data, path.name, sha256, parsed_at=parsed_at, lines=lines)
        if turnitin.detect_layout(lines) is not None:
            return turnitin.parse_pdf(data, path.name, sha256, parsed_at=parsed_at, lines=lines)
        raise AdapterError(t("adapters.unknown_pdf"))
    raise AdapterError(f"unsupported report type {suffix!r}; use {' or '.join(REPORT_SUFFIXES)}")
