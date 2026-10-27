"""Read a Turnitin Similarity Report downloaded as PDF into the common report schema.

Two layouts are recognised (``labels.yaml``):

- **Feedback Studio**: the paper, then an "ORIGINALITY REPORT" page with the similarity
  index, the per-database breakdown, the primary sources and the exclusions.
- **Enhanced Similarity Report**: a Cover Page, an Integrity Overview (overall similarity,
  filters, match groups, database breakdown, integrity flags, top sources) and the paper.

Neither layout exposes the matched passages as text (they are coloured highlights), so the
report carries sources but no matches, and the auditor uses its approximate method
(ADR 005). Following ADR 004, the adapter records what the report says, never invents a
value it could not read, adds a warning instead, and drops the author name and file name
shown on the report.
"""

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from functools import cache
from importlib.resources import files
from typing import Any, Final

import yaml
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from draftwitness import __version__
from draftwitness.adapters.base import AdapterError
from draftwitness.core.report_schema import (
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

ADAPTER_NAME: Final = "turnitin-pdf"
ADAPTER_VERSION: Final = "0.1"
FEEDBACK_STUDIO: Final = "feedback_studio"
ENHANCED: Final = "enhanced"
_PERCENT = re.compile(r"^(<\s*)?(\d+(?:[.,]\d+)?)\s*%$")
_RANK_ROW = re.compile(r"^(\d+)\s+(<\s*)?(\d+(?:[.,]\d+)?)\s*%$")
_MONTHS: Final = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}
_CLASSIC_DATE = re.compile(
    r"(\d{1,2})-([A-Za-z]{3})-(\d{4}) (\d{1,2}):(\d{2})\s*([AP]M)\s*\(UTC([+-])(\d{2}):?(\d{2})\)"
)
_ENHANCED_DATE = re.compile(
    r"([A-Za-z]{3}) (\d{1,2}), (\d{4}),? (\d{1,2}):(\d{2})\s*([AP]M)\s*"
    r"(?:GMT|UTC)(?:([+-])(\d{1,2})(?::?(\d{2}))?)?"
)


@cache
def labels() -> dict[str, Any]:
    text = files("draftwitness.adapters.turnitin").joinpath("labels.yaml").read_text("utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    return data


def _lines(data: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise AdapterError("the PDF is encrypted")
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise AdapterError(f"cannot read PDF: {exc}") from exc
    return normalized_lines("\n".join(pages))


def normalized_lines(text: str) -> list[str]:
    """Non-empty lines with ligatures expanded (NFKC: "Oﬀ" becomes "Off") and whitespace
    collapsed."""
    text = unicodedata.normalize("NFKC", text)
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _languages(layout: str) -> dict[str, dict[str, Any]]:
    """The label sets of ``layout``, by language code."""
    return {key: value for key, value in labels()[layout].items() if isinstance(value, dict)}


def detect_layout(lines: list[str]) -> tuple[str, str] | None:
    """``(layout, language)`` of the first label set that matches, or ``None``."""
    present = set(lines)
    for language, fs in _languages(FEEDBACK_STUDIO).items():
        if {fs["report_heading"], fs["overall"], fs["sources_heading"]} <= present:
            return FEEDBACK_STUDIO, language
    for language, en in _languages(ENHANCED).items():
        if en["overall"] in present and any(en["integrity_overview"] in line for line in lines):
            return ENHANCED, language
    return None


def _percent(text: str) -> tuple[float, bool] | None:
    match = _PERCENT.match(text)
    if match is None:
        return None
    return float(match.group(2).replace(",", ".")), bool(match.group(1))


def _number(text: str) -> int:
    return int(text.replace(",", "").replace(".", ""))


def _offset(sign: str | None, hours: str | None, minutes: str | None) -> timezone:
    if not sign or hours is None:
        return UTC
    delta = timedelta(hours=int(hours), minutes=int(minutes or 0))
    return timezone(delta if sign == "+" else -delta)


def _clock(hour: str, minute: str, half: str) -> tuple[int, int]:
    value = int(hour) % 12 + (12 if half.upper() == "PM" else 0)
    return value, int(minute)


def parse_classic_date(text: str) -> datetime | None:
    """``22-Sep-2023 04:02PM (UTC+0800)`` as an aware datetime."""
    match = _CLASSIC_DATE.search(text)
    if match is None or match.group(2).lower() not in _MONTHS:
        return None
    day, month, year = int(match.group(1)), _MONTHS[match.group(2).lower()], int(match.group(3))
    hour, minute = _clock(match.group(4), match.group(5), match.group(6))
    zone = _offset(match.group(7), match.group(8), match.group(9))
    return datetime(year, month, day, hour, minute, tzinfo=zone)


def parse_enhanced_date(text: str) -> datetime | None:
    """``Jul 11, 2026, 8:04 AM GMT+7`` as an aware datetime."""
    match = _ENHANCED_DATE.search(text)
    if match is None or match.group(1).lower() not in _MONTHS:
        return None
    month, day, year = _MONTHS[match.group(1).lower()], int(match.group(2)), int(match.group(3))
    hour, minute = _clock(match.group(4), match.group(5), match.group(6))
    zone = _offset(match.group(7), match.group(8), match.group(9))
    return datetime(year, month, day, hour, minute, tzinfo=zone)


@dataclass
class _Parsed:
    product: str
    submission: Submission = field(default_factory=Submission)
    overall: float | None = None
    filters: SimilarityFilters = field(default_factory=SimilarityFilters)
    sources: list[Source] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _value_before(lines: list[str], label: str, *, last: bool = False) -> tuple[float, bool] | None:
    indexes = [i for i, line in enumerate(lines) if line == label]
    if not indexes:
        return None
    index = indexes[-1] if last else indexes[0]
    return _percent(lines[index - 1]) if index > 0 else None


def _after_prefix(lines: list[str], prefix: str) -> str | None:
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _source(rank: int, label: str, kind: SourceKind, value: tuple[float, bool] | None) -> Source:
    return Source(
        id=f"s{rank}",
        rank=rank,
        label=label,
        kind=kind,
        url=None,
        percent=value[0] if value else None,
        percent_is_upper_bound=value[1] if value else False,
    )


# --- Feedback Studio ----------------------------------------------------------------------


def _fs_submission(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    head = lines[:20]
    date_text = _after_prefix(head, words["submission_date"])
    submitted = parse_classic_date(date_text) if date_text else None
    if date_text and submitted is None:
        parsed.warnings.append("The submission date could not be read.")
    word_count = _after_prefix(head, words["word_count"])
    characters = _after_prefix(head, words["character_count"])
    title = None
    if len(head) > 1 and head[1].startswith(words["author_prefix"]):
        title = head[0]  # head[1] is the author name, which is not kept
    parsed.submission = Submission(
        title=title,
        submission_id=_after_prefix(head, words["submission_id"]),
        submitted_at=submitted,
        word_count=_number(word_count) if word_count and word_count[0].isdigit() else None,
        character_count=_number(characters) if characters and characters[0].isdigit() else None,
    )


def _fs_filters(lines: list[str], words: dict[str, Any]) -> SimilarityFilters:
    def switch(label: str) -> bool | None:
        value = _after_prefix(lines, label)
        if value == words["switch_on"]:
            return True
        if value == words["switch_off"]:
            return False
        return None

    matches = _after_prefix(lines, words["exclude_matches"])
    small: dict[str, Any] = {}
    if matches == words["switch_off"]:
        small["small_matches_excluded"] = False
    elif matches:
        bound = re.match(
            r"^<\s*(\d+(?:[.,]\d+)?)\s*(%|" + re.escape(words["words"]) + ")$", matches
        )
        if bound:
            small["small_matches_excluded"] = True
            value = bound.group(1).replace(",", ".")
            if bound.group(2) == "%":
                small["small_matches_min_percent"] = float(value)
            else:
                small["small_matches_min_words"] = int(float(value))
    return SimilarityFilters(
        quotes_excluded=switch(words["exclude_quotes"]),
        bibliography_excluded=switch(words["exclude_bibliography"]),
        **small,
    )


def _fs_ranks(report: list[str]) -> dict[int, tuple[float, bool]]:
    """``rank → (percent, is_upper_bound)`` from rows such as ``3 <1%``."""
    ranks: dict[int, tuple[float, bool]] = {}
    for line in report:
        row = _RANK_ROW.match(line)
        if row:
            value = (float(row.group(3).replace(",", ".")), bool(row.group(2)))
            ranks.setdefault(int(row.group(1)), value)
    return ranks


def _fs_names(
    report: list[str], words: dict[str, Any], parsed: _Parsed
) -> list[tuple[str, SourceKind]]:
    """Source names and kinds, in list order. A name may wrap over several lines."""
    kinds: dict[str, str] = words["source_kinds"]
    skip = {words["report_heading"], words["sources_heading"]}
    excludes = (words["exclude_quotes"], words["exclude_bibliography"], words["exclude_matches"])
    page_marker = re.compile(rf"^{re.escape(words['page_marker'])} \d+$")
    names: list[tuple[str, SourceKind]] = []
    buffer: list[str] = []
    for line in report[report.index(words["sources_heading"]) + 1 :]:
        if page_marker.match(line):
            break
        if line in kinds:
            if buffer:
                names.append((" ".join(buffer), SourceKind(kinds[line])))
            else:
                parsed.warnings.append("A source in the list has no name.")
            buffer = []
        elif line in skip or _RANK_ROW.match(line) or _PERCENT.match(line):
            continue
        elif not line.startswith(excludes):
            buffer.append(line)
    if buffer and buffer != [parsed.submission.title]:
        parsed.warnings.append(
            "Some text after the source list was not recognised as a source and was ignored."
        )
    return names


def _feedback_studio(lines: list[str], words: dict[str, Any]) -> _Parsed:
    parsed = _Parsed(product="Feedback Studio")
    _fs_submission(lines, words, parsed)
    starts = [i for i, line in enumerate(lines) if line == words["overall"]]
    report = lines[starts[-1] - 1 :]
    overall = _percent(report[0])
    parsed.overall = overall[0] if overall else None
    databases = {}
    for key in ("database_internet", "database_publications", "database_student_papers"):
        value = _value_before(report, words[key])
        if value is not None:
            databases[key.removeprefix("database_")] = value[0]
    parsed.extensions["databases"] = databases
    parsed.filters = _fs_filters(report, words)

    ranks = _fs_ranks(report)
    names = _fs_names(report, words, parsed)
    if len(names) != len(ranks):
        parsed.warnings.append(
            f"The report lists {len(ranks)} source percentages but {len(names)} source names; "
            "they were paired in order and may be misaligned."
        )
    for rank, (label, kind) in enumerate(names, start=1):
        parsed.sources.append(_source(rank, label, kind, ranks.get(rank)))
    return parsed


# --- Enhanced Similarity Report -----------------------------------------------------------


def _count(lines: list[str], suffixes: list[str]) -> int | None:
    for line in lines:
        for suffix in suffixes:
            match = re.match(rf"^([\d.,]+) {re.escape(suffix)}$", line)
            if match:
                return _number(match.group(1))
    return None


def _next_value(lines: list[str], label: str) -> str | None:
    for index, line in enumerate(lines[:-1]):
        if line == label:
            return lines[index + 1]
    return None


def _enhanced_cover(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    try:
        details = lines.index(words["document_details"])
    except ValueError:
        parsed.warnings.append("The cover page was not found.")
        return
    cover = lines[details : details + 30]
    # The title and the author name come before "Document Details", in an order that varies
    # between reports. Only a line that equals the file name (Turnitin's default title) is
    # kept as the title; the author name is never kept.
    file_name = _next_value(cover, words["file_name"]) or ""
    names = {file_name, file_name.rsplit(".", 1)[0]} - {""}
    title = next((line for line in lines[:details] if line in names), None)
    if title is None:
        parsed.warnings.append(
            "The submission title could not be told apart from the author name on the cover "
            "page, so neither was kept."
        )
    date_text = _next_value(cover, words["submission_date"])
    submitted = parse_enhanced_date(date_text) if date_text else None
    if date_text and submitted is None:
        parsed.warnings.append("The submission date could not be read.")
    parsed.submission = Submission(
        title=title or None,
        submission_id=_next_value(cover, words["submission_id"]),
        submitted_at=submitted,
        page_count=_count(cover, words["pages"]),
        word_count=_count(cover, words["words"]),
        character_count=_count(cover, words["characters"]),
    )


def _section(lines: list[str], heading: str, ends: set[str]) -> list[str]:
    if heading not in lines:
        return []
    start = lines.index(heading) + 1
    for index in range(start, len(lines)):
        if lines[index] in ends:
            return lines[start:index]
    return lines[start:]


def _enhanced_filters(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    ends = {words["exclusions_heading"], words["match_groups_heading"]}
    if words["filtered_heading"] not in lines:
        return
    found: dict[str, bool] = {}
    min_words = None
    for item in _section(lines, words["filtered_heading"], ends):
        for label, key in words["filters"].items():
            if item.startswith(label):
                found[key] = True
                bound = re.search(r"(\d+)\s+words?", item)
                if key == "small_matches" and bound:
                    min_words = int(bound.group(1))
                if label in words["filters_needing_verification"]:
                    parsed.warnings.append(
                        f"The filter label “{label}” has not yet been checked against a real "
                        "report; check the filters shown on yours."
                    )
                break
        else:
            parsed.warnings.append(f"Unrecognised filter on the report: “{item}”.")
    parsed.filters = SimilarityFilters(
        quotes_excluded=found.get("quotes", False),
        bibliography_excluded=found.get("bibliography", False),
        small_matches_excluded=found.get("small_matches", False),
        small_matches_min_words=min_words,
    )
    parsed.extensions["cited_text_excluded"] = found.get("cited", False)


def _enhanced_overview(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    overall = _value_before(lines, words["overall"])
    parsed.overall = overall[0] if overall else None
    _enhanced_filters(lines, words, parsed)
    exclusions = _section(lines, words["exclusions_heading"], {words["match_groups_heading"]})
    for key, label in (
        ("excluded_matches", "excluded_matches"),
        ("excluded_sources", "excluded_sources"),
    ):
        count = _count(exclusions, [words[label]])
        if count is not None:
            parsed.extensions[key] = count
    groups: dict[str, dict[str, float | int]] = {}
    for index, line in enumerate(lines):
        for label, key in words["match_groups"].items():
            match = re.match(rf"^{re.escape(label)}\s+(<?\s*\d+(?:[.,]\d+)?\s*%)$", line)
            if match and key not in groups and index > 0 and lines[index - 1].isdigit():
                value = _percent(match.group(1))
                if value is not None:
                    groups[key] = {"matches": int(lines[index - 1]), "percent": value[0]}
    parsed.extensions["match_groups"] = groups
    databases = {}
    for label, key in words["databases"].items():
        value = _value_before(lines, label)
        if value is not None:
            databases[key] = value[0]
    parsed.extensions["databases"] = databases
    flags = _count(lines, [words["integrity_flags"]])
    if flags is not None:
        parsed.extensions["integrity_flags"] = flags


def _enhanced_sources(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    intro = [i for i, line in enumerate(lines) if line.startswith(words["top_sources_intro"])]
    if not intro:
        return
    footer = re.compile(
        "^"
        + re.escape(words["page_footer"]).replace(r"\{page\}", r"\d+").replace(r"\{pages\}", r"\d+")
        + "(.+)$"
    )
    kinds: dict[str, str] = words["source_kinds"]
    index, end = intro[0] + 1, len(lines)
    truncated = False
    while index < end:
        line = lines[index]
        section = footer.match(line)
        if section:
            if section.group(1) != words["integrity_overview"]:
                break
            index += 1
        elif line == words["submission_id"]:
            index += 2
        elif line.isdigit() and index + 1 < end and lines[index + 1] in kinds:
            rank, kind = int(line), SourceKind(kinds[lines[index + 1]])
            index += 2
            label: list[str] = []
            while index < end and _percent(lines[index]) is None and len(label) < 4:
                label.append(lines[index])
                index += 1
            value = _percent(lines[index]) if index < end else None
            name = " ".join(label)
            truncated = truncated or name.endswith("...")
            if name:
                parsed.sources.append(_source(rank, name, kind, value))
            index += 1
        else:
            break
    if truncated:
        parsed.warnings.append("The report shortens long source names; they end in “...”.")
    ranks = [source.rank for source in parsed.sources]
    if ranks != list(range(1, len(ranks) + 1)):
        parsed.warnings.append(
            "The source list is not numbered 1, 2, 3…; some rows may be missing."
        )


def _enhanced(lines: list[str], words: dict[str, Any]) -> _Parsed:
    parsed = _Parsed(product="Similarity Report")
    _enhanced_cover(lines, words, parsed)
    _enhanced_overview(lines, words, parsed)
    _enhanced_sources(lines, words, parsed)
    return parsed


# --- Report -------------------------------------------------------------------------------


def _check(parsed: _Parsed) -> None:
    if parsed.overall is None:
        return
    for source in parsed.sources:
        if source.percent is not None and source.percent > parsed.overall:
            parsed.warnings.append(
                f"Source {source.rank} is shown with {source.percent:g}%, more than the overall "
                f"{parsed.overall:g}%: the report may have been misread or edited."
            )


def parse_pdf(data: bytes, filename: str, sha256: str, *, parsed_at: datetime) -> Report:
    """Turn a downloaded Turnitin PDF report into a :class:`Report`."""
    lines = _lines(data)
    detected = detect_layout(lines)
    if detected is None:
        raise AdapterError(
            "not a Turnitin Similarity Report layout DraftWitness recognises (Feedback Studio "
            f"or the enhanced Similarity Report, in: {', '.join(sorted(_languages(ENHANCED)))})"
        )
    layout, language = detected
    words = _languages(layout)[language]
    parse = _feedback_studio if layout == FEEDBACK_STUDIO else _enhanced
    parsed = parse(lines, words)
    if parsed.overall is None:
        raise AdapterError("the overall similarity percentage could not be read")
    _check(parsed)
    parsed.warnings.append(
        "Turnitin PDF reports show matched passages only as coloured highlights, so the "
        "report has sources but no matched text; the audit uses its approximate method."
    )
    if not parsed.sources:
        parsed.warnings.append("No source list was read from the report.")
    turnitin: dict[str, Any] = {"layout": layout, "language": language, **parsed.extensions}
    return Report(
        tool=Tool(name="turnitin", product=parsed.product, report_kind=ReportKind.SIMILARITY),
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
        submission=parsed.submission,
        similarity=Similarity(
            overall_percent=parsed.overall, filters=parsed.filters, sources=parsed.sources
        ),
        warnings=parsed.warnings,
        extensions={"turnitin": turnitin},
    )
