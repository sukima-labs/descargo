"""What the two Compilatio layouts share: labels, number formats and the report they build."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from functools import cache
from importlib.resources import files
from typing import Any, Final

import yaml

from draftwitness import __version__
from draftwitness.core.report_schema import (
    AiWriting,
    Provenance,
    Report,
    ReportFile,
    ReportKind,
    Similarity,
    Source,
    Submission,
    Tool,
)

ADAPTER_NAME: Final = "compilatio-pdf"
ADAPTER_VERSION: Final = "0.2"
AI_COLOUR: Final = (0.0, 0.75, 1.0)
"""Colour of what Compilatio attributes to AI, as RGB from 0 to 1: the text itself in the
Magister layout, a line under the text in Magister+."""
TOLERANCE: Final = 0.02
NUMBER: Final = r"(<\s*)?(\d+(?:[.,]\d+)?)\s*%"
_NUMERIC_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_WORDED_DATE = re.compile(r"(\d{1,2}) de (\w+) de (\d{4})")

Words = dict[str, Any]


@cache
def labels() -> dict[str, dict[str, Words]]:
    """``labels.yaml``: layout, then language, then label key."""
    text = files("draftwitness.adapters.compilatio").joinpath("labels.yaml").read_text("utf-8")
    data: dict[str, dict[str, Words]] = yaml.safe_load(text)
    return data


def value(match: re.Match[str], group: int = 1) -> tuple[float, bool]:
    """The percentage a :data:`NUMBER` match starting at ``group`` holds, and whether the
    report shows it as an upper bound ("<1%")."""
    return float(match.group(group + 1).replace(",", ".")), bool(match.group(group))


def percent_before(text: str, label: str) -> tuple[float, bool] | None:
    """The percentage just before ``label`` in ``text``, or ``None``."""
    match = re.search(rf"{NUMBER}\s*{re.escape(label)}", text)
    return value(match) if match else None


def after(lines: list[str], label: str, stop: str | None = None) -> str | None:
    """The text after ``label`` on its line; with ``stop``, also the lines that follow it
    up to the one starting with ``stop`` (a value that wraps)."""
    for index, line in enumerate(lines):
        if line.startswith(label):
            parts = [line[len(label) :].strip()]
            if stop is not None:
                for following in lines[index + 1 : index + 4]:
                    if following.startswith(stop):
                        break
                    parts.append(following)
                else:
                    parts = parts[:1]
            return " ".join(part for part in parts if part) or None
    return None


def count(text: str | None) -> int | None:
    digits = (text or "").replace(".", "").replace(",", "").replace(" ", "")
    return int(digits) if digits.isdigit() else None


def day(text: str | None, months: list[str] | None = None) -> str | None:
    """A date shown as "5/9/2025" or, with ``months``, as "23 de marzo de 2026"."""
    try:
        match = _NUMERIC_DATE.search(text or "")
        if match:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
        match = _WORDED_DATE.search(text or "")
        if match and months and match.group(2).lower() in months:
            month = months.index(match.group(2).lower()) + 1
            return date(int(match.group(3)), month, int(match.group(1))).isoformat()
    except ValueError:
        return None
    return None


def same(colour: tuple[float, ...] | None, wanted: tuple[float, ...]) -> bool:
    return (
        colour is not None
        and len(colour) == len(wanted)
        and all(abs(a - b) <= TOLERANCE for a, b in zip(colour, wanted, strict=True))
    )


def joined_runs(runs: list[list[tuple[float, str]]]) -> list[str]:
    """Each run of ``(baseline, text)`` pieces as one string. Pieces on different lines are
    joined with a space."""
    texts = []
    for run in runs:
        joined = ""
        last_y: float | None = None
        for y, piece in run:
            wrapped = last_y is not None and y != last_y
            if wrapped and joined and not joined[-1].isspace() and not piece[:1].isspace():
                joined += " "
            joined += piece
            last_y = y
        text = " ".join(unicodedata.normalize("NFKC", joined).split())
        if text:
            texts.append(text)
    return texts


def overlap_warnings(sources: list[Source], ceiling: float, label: str) -> list[str]:
    """A source can match no more of the document than the report's ``ceiling``."""
    return [
        f"Source {source.label} is shown with {source.percent:g}%, more than the {label} "
        f"{ceiling:g}%: the report may have been misread or edited."
        for source in sources
        if source.percent is not None and source.percent > ceiling
    ]


@dataclass(frozen=True)
class Download:
    """The downloaded PDF the report is read from."""

    data: bytes
    filename: str
    sha256: str
    parsed_at: datetime


def submission(name: str | None, word_count: int | None, character_count: int | None) -> Submission:
    """The document's details; its title is the file name without the extension."""
    return Submission(
        title=name.rsplit(".", 1)[0] if name else None,
        word_count=word_count,
        character_count=character_count,
    )


def build_report(
    download: Download,
    product: str,
    submitted: Submission,
    similarity: Similarity,
    ai_writing: AiWriting | None,
    warnings: list[str],
    extensions: dict[str, Any],
) -> Report:
    warnings.append(
        "Compilatio PDF reports show matched passages only as highlights, so the report has "
        "sources but no matched text; the audit uses its approximate method."
    )
    return Report(
        tool=Tool(name="compilatio", product=product, report_kind=ReportKind.COMBINED),
        provenance=Provenance(
            adapter=ADAPTER_NAME,
            adapter_version=ADAPTER_VERSION,
            draftwitness_version=__version__,
            parsed_at=download.parsed_at,
            report_file=ReportFile(
                filename=download.filename,
                media_type="application/pdf",
                sha256=download.sha256,
                size_bytes=len(download.data),
            ),
        ),
        submission=submitted,
        similarity=similarity,
        ai_writing=ai_writing,
        warnings=warnings,
        extensions={"compilatio": extensions},
    )
