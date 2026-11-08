"""Read Turnitin's AI Writing Report from a downloaded PDF (ADR 009).

The report opens with an AI Writing Overview: the share of the submission Turnitin
attributes to AI ("23% detected as AI") and, when it is shown, the detection groups behind
it. Under its 20 % threshold Turnitin gives no figure, only "*%", and highlights nothing.
The pages after the overview are the paper, with each passage Turnitin attributes to AI
drawn on a cyan rectangle; those passages are read from the rectangles. Text that was also
AI-paraphrased is highlighted purple, a colour not yet seen in a real report, so it is not
read and the import says so.

The AI Writing Report may be downloaded on its own or in one PDF after the Similarity
Report; its own pages are told apart by their footer ("Page 3 of 11 - AI Writing
Submission"), whose page total differs from the Similarity Report's.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pypdf import PdfReader

from descargo.adapters.base import AdapterError
from descargo.adapters.highlights import read_page, runs
from descargo.core.report_schema import AiSegment, AiWriting
from descargo.i18n import t

_SCORE = r"(<\s*)?(\*|\d+(?:[.,]\d+)?)\s*%"
_PERCENT = re.compile(rf"^{_SCORE}$")

#: ``(section, total pages)`` of each page footer on a page, given that page's lines.
Footers = Callable[[list[str]], list[tuple[str, int]]]


@dataclass
class AiParsed:
    """What the AI Writing Report says."""

    ai_writing: AiWriting
    extensions: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _score(lines: list[str], detected: str) -> tuple[str, float | None, bool] | None:
    """The line with the overall result, its percentage (``None`` for "*%") and whether it
    is an upper bound."""
    pattern = re.compile(rf"^{_SCORE}\s+{re.escape(detected)}$")
    for line in lines:
        match = pattern.match(line)
        if match:
            value = None if match.group(2) == "*" else float(match.group(2).replace(",", "."))
            return line, value, bool(match.group(1))
    return None


def has_overview(lines: list[str], words: dict[str, Any], footers: Footers) -> bool:
    """Whether ``lines`` hold an AI Writing Overview in ``words``' language."""
    sections = {section for section, _ in footers(lines)}
    return words["overview"] in sections and _score(lines, words["detected"]) is not None


def _groups(lines: list[str], words: dict[str, Any]) -> dict[str, float]:
    """``group → percent`` for each detection group shown: its label, then its percentage
    on the next line."""
    groups: dict[str, float] = {}
    for index, line in enumerate(lines[:-1]):
        key = words["groups"].get(line)
        match = _PERCENT.match(lines[index + 1])
        if key and key not in groups and match and match.group(2) != "*":
            groups[key] = float(match.group(2).replace(",", "."))
    return groups


def _segments(
    reader: PdfReader, words: dict[str, Any], footers: Footers, colour: tuple[float, ...]
) -> tuple[list[AiSegment], int, int | None]:
    """The highlighted passages on the AI Writing Report's own pages, the number of those
    pages that show the paper, and the report's page total."""
    pages = [read_page(page, n, colour) for n, page in enumerate(reader.pages, start=1)]
    total = next(
        (
            pages_in
            for page in pages
            for section, pages_in in footers(page.lines)
            if section == words["overview"]
        ),
        None,
    )
    segments: list[AiSegment] = []
    paper_pages = 0
    for page in pages:
        own = [
            section
            for section, pages_in in footers(page.lines)
            if pages_in == total and section not in {words["overview"], *words["skip_sections"]}
        ]
        if not own:
            continue
        paper_pages += 1
        if page.rects:
            segments += [AiSegment(text=text, page=page.number) for text in runs(page)]
    return segments, paper_pages, total


def parse_ai(
    reader: PdfReader,
    lines: list[str],
    words: dict[str, Any],
    footers: Footers,
    colour: tuple[float, ...],
) -> AiParsed:
    """The AI Writing Report in ``reader``, whose text is ``lines``. ``words`` are the
    language's labels, with ``skip_sections``: the footer sections that are not the paper
    (the cover page)."""
    score = _score(lines, words["detected"])
    if score is None:
        raise AdapterError("the AI writing percentage could not be read")
    shown, percent, upper_bound = score
    below = percent is None
    groups = _groups(lines, words)
    segments, paper_pages, total = _segments(reader, words, footers, colour)
    parsed = AiParsed(
        ai_writing=AiWriting(
            overall_percent=percent,
            label=shown if below else None,
            segments=segments,
        ),
        extensions={
            "below_threshold": below,
            "percent_is_upper_bound": upper_bound,
            "groups": groups,
            "report_pages": total,
        },
    )
    if below:
        parsed.warnings.append(t("adapters.warn_ai_below_threshold"))
    if groups.get("ai_paraphrased"):
        parsed.warnings.append(
            t("adapters.warn_ai_paraphrased", percent=f"{groups['ai_paraphrased']:g}")
        )
    if percent and not segments:
        parsed.warnings.append(
            t("adapters.warn_ai_no_paper" if paper_pages == 0 else "adapters.warn_ai_no_highlights")
        )
    return parsed
