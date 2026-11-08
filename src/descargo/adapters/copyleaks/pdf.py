"""Read a Copyleaks report downloaded as PDF into the common report schema (ADR 004, 009).

Two layouts are recognised (``labels.yaml``):

- **2023**, the "Plagiarism and AI Content Detector Report" (or "Plagiarism report"): a
  summary with the overall similarity split by match type (identical, minor changes,
  paraphrased), the share of the text Copyleaks attributes to AI, the alerts it raises and
  the list of sources, then the submitted text and, when AI was found, the text again with
  the passages Copyleaks attributes to AI on coloured rectangles.
- **2022**, an earlier export with the similarity summary and the sources but no AI result.

Each source's share is shown split by match type. Its percentage here is the sum of those
shares, as the report's overall similarity is the sum of its own (checked on three real
reports). Matched passages are only highlights that do not say which source they match, so
the report carries sources but no matched passages, and the auditor uses its approximate
method (ADR 005). The passages attributed to AI are read from the darkest colour of
Copyleaks' AI scale, the only one seen in a real report; the import warns when they do not
add up to the share Copyleaks gives. Following ADR 004, the adapter never keeps the name of
who submitted the scan or the scan id, never invents a value it could not read, and adds a
warning instead.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from importlib.resources import files
from typing import Any, Final

import yaml
from pypdf import PdfReader

from descargo import __version__
from descargo.adapters.base import AdapterError
from descargo.adapters.highlights import read_page, runs
from descargo.adapters.pdftext import open_pdf, pdf_lines
from descargo.core.report_schema import (
    AiSegment,
    AiWriting,
    Provenance,
    Report,
    ReportFile,
    ReportKind,
    Similarity,
    Source,
    SourceKind,
    Submission,
    Tool,
)
from descargo.i18n import t

ADAPTER_NAME: Final = "copyleaks-pdf"
ADAPTER_VERSION: Final = "0.1"
#: Fill of the darkest step of Copyleaks' AI scale (shown as "99%"), RGB from 0 to 1. The
#: lighter steps (20 % to 80 %) have not been seen in a real report.
AI_COLOUR: Final = (1.0, 0.4, 0.4)
#: How far, in percentage points, the words read as AI may be from Copyleaks' share before
#: the import warns.
AI_SLACK: Final = 2.0
_NUMBER = r"(\d+(?:\.\d+)?)%"
_SUMMARY = re.compile(rf"^{_NUMBER} (?:{_NUMBER}|N/A)$")
_SEVERITY = re.compile(r"^(\d)/(\d) Severity$")
_COUNT = re.compile(r"\((\d+)\)")
_SCAN_TIME = re.compile(r"(\w+) (\d{1,2})(?:st|nd|rd|th)?, (\d{4}) at (\d{1,2}):(\d{2}) UTC")
_SCANNED_ON = re.compile(r"(\d{1,2}):(\d{2}) (\w+) (\d{1,2}), (\d{4}) UTC")
_MONTHS: Final = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

Words = dict[str, Any]


@cache
def labels() -> dict[str, dict[str, Words]]:
    """``labels.yaml``: layout, then language, then label key."""
    text = files("descargo.adapters.copyleaks").joinpath("labels.yaml").read_text("utf-8")
    data: dict[str, dict[str, Words]] = yaml.safe_load(text)
    return data


def _squeezed(line: str) -> str:
    """``line`` without spaces: Copyleaks letter-spaces its headings ("R e s u l t s")."""
    return line.replace(" ", "")


def _is_2023(lines: list[str], words: Words) -> bool:
    return (
        bool(lines)
        and _squeezed(lines[0]) in words["headings"]
        and words["scan_details"] in lines[:6]
        and words["plagiarism_detection"] in lines
    )


def _is_2022(lines: list[str], words: Words) -> bool:
    return (
        any(line.startswith(words["scanned_on"]) for line in lines[:4])
        and words["overall"] in lines
        and words["sources_intro"] in lines
    )


_LAYOUTS: Final = {"report_2023": _is_2023, "report_2022": _is_2022}


def detect_layout(lines: list[str]) -> tuple[str, str] | None:
    """The layout and language of the Copyleaks report whose lines these are, or ``None``."""
    for layout, recognises in _LAYOUTS.items():
        for language, words in labels()[layout].items():
            if recognises(lines, words):
                return layout, language
    return None


def _after(lines: list[str], label: str) -> str | None:
    """The line after the one that is ``label``."""
    for index, line in enumerate(lines[:-1]):
        if line == label:
            return lines[index + 1]
    return None


def _count(text: str | None) -> int | None:
    digits = (text or "").replace(",", "")
    return int(digits) if digits.isdigit() else None


def _scan_time(text: str | None) -> datetime | None:
    """ "April 24th, 2023 at 9:16 UTC" (2023) or "8:52 October 30, 2022 UTC" (2022)."""
    try:
        match = _SCAN_TIME.search(text or "")
        if match and match.group(1).lower() in _MONTHS:
            month = _MONTHS.index(match.group(1).lower()) + 1
            day, year, hour, minute = (int(match.group(n)) for n in (2, 3, 4, 5))
            return datetime(year, month, day, hour, minute, tzinfo=UTC)
        match = _SCANNED_ON.search(text or "")
        if match and match.group(3).lower() in _MONTHS:
            month = _MONTHS.index(match.group(3).lower()) + 1
            hour, minute, day, year = (int(match.group(n)) for n in (1, 2, 4, 5))
            return datetime(year, month, day, hour, minute, tzinfo=UTC)
    except ValueError:
        return None
    return None


@dataclass
class _Block:
    """One source in the 2023 list: its text lines, then its percentages."""

    text: list[str] = field(default_factory=list)
    types: dict[str, float] = field(default_factory=dict)
    total: float | None = None

    @property
    def closed(self) -> bool:
        return bool(self.types) or self.total is not None


def _percent_line(line: str, words: Words) -> tuple[str | None, float] | None:
    """``(type, percent)`` for "Identical 2.6%", ``(None, percent)`` for "99.4%"."""
    match = re.fullmatch(_NUMBER, line)
    if match:
        return None, float(match.group(1))
    for label, key in words["types"].items():
        match = re.fullmatch(rf"{re.escape(label)} {_NUMBER}", line)
        if match:
            return key, float(match.group(1))
    return None


def _source_blocks(lines: list[str], words: Words) -> tuple[list[_Block], int | None]:
    """The source list and the number of results the report announces."""
    start = next((i for i, line in enumerate(lines) if line.startswith(words["results"])), None)
    if start is None:
        return [], None
    announced = _COUNT.search(lines[start])
    furniture = set(words["furniture"])
    blocks: list[_Block] = []
    current = _Block()
    for line in lines[start + 1 :]:
        if line in words["report_content"] or any(
            line.startswith(end) for end in words["end_of_results"]
        ):
            break
        if _squeezed(line) in furniture or line in furniture or _SUMMARY.match(line):
            continue
        percent = _percent_line(line, words)
        if percent is None:
            if current.closed:
                blocks.append(current)
                current = _Block()
            current.text.append(line)
            continue
        kind, value = percent
        repeated = current.total is not None if kind is None else kind in current.types
        if repeated:
            blocks.append(current)
            current = _Block()
        if kind is None:
            current.total = value
        else:
            current.types[kind] = value
    if current.closed:
        blocks.append(current)
    return blocks, int(announced.group(1)) if announced else None


def _source(rank: int, block: _Block, words: Words) -> Source | None:
    if not block.text:
        return None
    label = block.text[0]
    url = next((line for line in block.text[1:2] if line.startswith("http")), None)
    internal = label == words["internal_database"]
    percent = block.total
    if percent is None and block.types:
        percent = round(sum(block.types.values()), 1)
    return Source(
        id=f"s{rank}",
        rank=rank,
        label=label,
        kind=SourceKind.OTHER if internal else SourceKind.INTERNET if url else SourceKind.UNKNOWN,
        url=url,
        percent=percent,
    )


def _types(lines: list[str], words: Words) -> dict[str, dict[str, float | int]]:
    """``type → {percent, words}`` from the summary rows ("Identical 22.9% 44")."""
    found: dict[str, dict[str, float | int]] = {}
    for label, key in words["types"].items():
        pattern = re.compile(rf"^{re.escape(label)} {_NUMBER} (\d+)$")
        for line in lines:
            match = pattern.match(line)
            if match:
                found[key] = {"percent": float(match.group(1)), "words": int(match.group(2))}
                break
    return found


def _ai_share(lines: list[str], words: Words, label: str) -> tuple[float, int] | None:
    pattern = re.compile(rf"^{re.escape(label)} {_NUMBER} (\d+)$")
    for line in lines:
        match = pattern.match(line)
        if match:
            return float(match.group(1)), int(match.group(2))
    return None


def _alerts(lines: list[str], words: Words) -> list[dict[str, Any]]:
    """Each alert's title and severity: the title, its explanation, then "2/5 Severity"."""
    start = next((i for i, line in enumerate(lines) if line.startswith(words["alerts"])), None)
    if start is None:
        return []
    alerts: list[dict[str, Any]] = []
    title: str | None = None
    for line in lines[start + 1 :]:
        if line.startswith(words["results"]):
            break
        severity = _SEVERITY.match(line)
        if severity:
            if title:
                alerts.append(
                    {
                        "title": title,
                        "severity": int(severity.group(1)),
                        "of": int(severity.group(2)),
                    }
                )
            title = None
        elif title is None:
            title = line
    return alerts


def _ai_segments(reader: PdfReader, words: Words) -> list[AiSegment]:
    """The passages on Copyleaks' AI colour, on the pages that show the scanned AI content."""
    segments: list[AiSegment] = []
    for number, page in enumerate(reader.pages, start=1):
        drawn = read_page(page, number, AI_COLOUR)
        if words["ai_content"] in drawn.lines and drawn.rects:
            segments += [AiSegment(text=text, page=number) for text in runs(drawn)]
    return segments


def _parse_2023(reader: PdfReader, lines: list[str], words: Words) -> tuple[Any, ...]:
    warnings: list[str] = []
    title = lines[1] if len(lines) > 1 and lines[1] != words["scan_details"] else None
    submitted = Submission(
        title=title,
        word_count=_count(_after(lines, words["total_words"])),
        page_count=_count(_after(lines, words["total_pages"])),
    )
    scanned_at = _scan_time(_after(lines, words["scan_time"]))
    if scanned_at is None:
        warnings.append(t("adapters.warn_copyleaks_scan_time"))
    summary = next((m for m in map(_SUMMARY.match, lines) if m), None)
    types = _types(lines, words)
    matched = {key: value for key, value in types.items() if key != "omitted"}
    if summary:
        overall = float(summary.group(1))
    elif matched:
        overall = round(sum(float(v["percent"]) for v in matched.values()), 1)
        warnings.append(t("adapters.warn_copyleaks_overall_sum", percent=f"{overall:g}"))
    else:
        raise AdapterError("the overall similarity could not be read")
    blocks, announced = _source_blocks(lines, words)
    sources: list[Source] = []
    for block in blocks:
        source = _source(len(sources) + 1, block, words)
        if source is None:
            warnings.append(t("adapters.warn_source_no_name"))
        else:
            sources.append(source)
    if announced is not None and announced != len(sources):
        warnings.append(
            t("adapters.warn_copyleaks_source_count", announced=announced, read=len(sources))
        )
    if any(source.label.endswith("...") for source in sources):
        warnings.append(t("adapters.warn_shortened_names"))
    ai_writing, ai_extensions = _ai(reader, lines, words, summary, warnings)
    extensions = {
        "layout": "report_2023",
        "scanned_at": scanned_at.isoformat() if scanned_at else None,
        "match_types": types,
        "alerts": _alerts(lines, words),
        "source_shares_by_type": {
            f"s{index}": block.types
            for index, block in enumerate((b for b in blocks if b.text), start=1)
            if block.types
        },
        **ai_extensions,
    }
    similarity = Similarity(overall_percent=overall, sources=sources)
    return submitted, similarity, ai_writing, warnings, extensions


def _ai(
    reader: PdfReader,
    lines: list[str],
    words: Words,
    summary: re.Match[str] | None,
    warnings: list[str],
) -> tuple[AiWriting | None, dict[str, Any]]:
    """The AI result, or ``None`` when the report shows "N/A" (no AI scan)."""
    share = _ai_share(lines, words, words["ai_text"])
    human = _ai_share(lines, words, words["human_text"])
    if share is None:
        if summary is not None and summary.group(2) is None:
            warnings.append(t("adapters.warn_copyleaks_ai_na"))
        return None, {"ai_result": "not_available"}
    percent, ai_words = share
    segments = _ai_segments(reader, words) if percent else []
    read_words = sum(len((segment.text or "").split()) for segment in segments)
    total_words = ai_words + (human[1] if human else 0)
    if percent and not segments:
        warnings.append(t("adapters.warn_ai_no_highlights"))
    elif percent and total_words:
        read_share = 100 * read_words / total_words
        if abs(read_share - percent) > AI_SLACK:
            warnings.append(
                t(
                    "adapters.warn_copyleaks_ai_shades",
                    read=f"{read_share:.0f}",
                    percent=f"{percent:g}",
                )
            )
    extensions = {"ai_words": ai_words, "human_words": human[1] if human else None}
    return AiWriting(overall_percent=percent, segments=segments), extensions


def _parse_2022(lines: list[str], words: Words) -> tuple[Any, ...]:
    warnings: list[str] = []
    overall_text = _after(lines, words["overall"])
    match = re.fullmatch(_NUMBER, overall_text or "")
    if match is None:
        raise AdapterError("the overall similarity could not be read")
    overall = float(match.group(1))
    scanned = next((line for line in lines if line.startswith(words["scanned_on"])), None)
    title = next((lines[i - 1] for i, line in enumerate(lines) if line == scanned and i), None)
    submitted = Submission(
        title=title.rsplit(".", 1)[0] if title else None,
        word_count=_count(_after(lines, words["total_words"])),
    )
    names = _names_2022(lines, words)
    percents = [float(m.group(1)) for m in (re.fullmatch(_NUMBER, line) for line in lines) if m][
        1:
    ]  # the first is the overall score
    if len(percents) != len(names):
        warnings.append(t("adapters.warn_misaligned", percentages=len(percents), names=len(names)))
    sources = [
        Source(
            id=f"s{rank}",
            rank=rank,
            label=label,
            kind=SourceKind.INTERNET if url else SourceKind.UNKNOWN,
            url=url,
            percent=percents[rank - 1] if rank <= len(percents) else None,
        )
        for rank, (label, url) in enumerate(names, start=1)
    ]
    announced = _count(_after(lines, words["results_found"]))
    if announced is not None and announced != len(sources):
        warnings.append(
            t("adapters.warn_copyleaks_source_count", announced=announced, read=len(sources))
        )
    if any(source.label.endswith("...") for source in sources):
        warnings.append(t("adapters.warn_shortened_names"))
    types = {
        key: {"words": value}
        for key, label in (
            ("identical", "identical_words"),
            ("minor_changes", "minor_changes_words"),
            ("paraphrased", "paraphrased_words"),
            ("omitted", "omitted_words"),
        )
        if (value := _count(_label_value(lines, words[label]))) is not None
    }
    scanned_at = _scan_time(scanned)
    if scanned_at is None:
        warnings.append(t("adapters.warn_copyleaks_scan_time"))
    extensions = {
        "layout": "report_2022",
        "scanned_at": scanned_at.isoformat() if scanned_at else None,
        "match_types": types,
    }
    return (
        submitted,
        Similarity(overall_percent=overall, sources=sources),
        None,
        warnings,
        extensions,
    )


def _label_value(lines: list[str], label: str) -> str | None:
    """The number after ``label`` on its own line ("Identical Words 76")."""
    for line in lines:
        if line.startswith(label + " "):
            return line[len(label) + 1 :]
    return None


def _names_2022(lines: list[str], words: Words) -> list[tuple[str, str | None]]:
    """Source names with their URL, in list order: a name, then a line with its URL (and,
    for long URLs, a second line with the rest of the address, which is ignored)."""
    names: list[tuple[str, str | None]] = []
    furniture = set(words["furniture"])
    start = lines.index(words["sources_intro"]) + 1
    for index in range(start, len(lines) - 1):
        line, following = lines[index], lines[index + 1]
        if line == words["scanned_text"]:
            break
        if line in furniture or line.startswith("http") or re.fullmatch(_NUMBER, line):
            continue
        if line.startswith(words["scanned_on"]) or lines[index + 1].startswith(words["scanned_on"]):
            continue
        if following.startswith("http"):
            names.append((line, following))
    return names


def parse_pdf(
    data: bytes,
    filename: str,
    sha256: str,
    *,
    parsed_at: datetime,
    lines: list[str] | None = None,
) -> Report:
    """Turn a downloaded Copyleaks PDF report into a :class:`Report`. ``lines`` are the
    report's :func:`~descargo.adapters.pdftext.pdf_lines`, if already extracted."""
    reader = open_pdf(data)
    lines = pdf_lines(data) if lines is None else lines
    found = detect_layout(lines)
    if found is None:
        raise AdapterError("not a Copyleaks report Descargo can read")
    layout, language = found
    words = labels()[layout][language]
    if layout == "report_2023":
        submitted, similarity, ai_writing, warnings, extensions = _parse_2023(reader, lines, words)
    else:
        submitted, similarity, ai_writing, warnings, extensions = _parse_2022(lines, words)
    if not similarity.sources:
        warnings.append(t("adapters.warn_no_source_list"))
    warnings.append(t("adapters.warn_copyleaks_highlights"))
    return Report(
        tool=Tool(
            name="copyleaks",
            report_kind=ReportKind.COMBINED if ai_writing else ReportKind.SIMILARITY,
        ),
        provenance=Provenance(
            adapter=ADAPTER_NAME,
            adapter_version=ADAPTER_VERSION,
            draftwitness_version=__version__,
            parsed_at=parsed_at,
            report_file=ReportFile(
                filename=filename,
                media_type="application/pdf",
                sha256=sha256,
                size_bytes=len(data),
            ),
        ),
        submission=submitted,
        similarity=similarity,
        ai_writing=ai_writing,
        warnings=warnings,
        extensions={"copyleaks": extensions},
    )
