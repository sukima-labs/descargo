"""Read a Turnitin report downloaded as PDF into the common report schema.

Three layouts are recognised (``labels.yaml``):

- **Feedback Studio**: the paper, then an "ORIGINALITY REPORT" page with the similarity
  index, the per-database breakdown, the primary sources and the exclusions.
- **Enhanced Similarity Report**: a Cover Page, an Integrity Overview (overall similarity,
  filters, match groups, database breakdown, integrity flags, top sources) and the paper.
- **AI Writing Report** (:mod:`.ai`), on its own or after an enhanced Similarity Report in
  the same PDF, which is then read as a combined report.

Neither Similarity Report layout exposes the matched passages as text (they are coloured
highlights), so the report carries sources but no matches, and the auditor uses its
approximate method (ADR 005). Following ADR 004, the adapter records what the report says,
never invents a value it could not read, adds a warning instead, and drops the author name
and file name shown on the report.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from functools import cache
from importlib.resources import files
from typing import Any, Final

import yaml

from draftwitness import __version__
from draftwitness.adapters.base import AdapterError
from draftwitness.adapters.pdftext import open_pdf, pdf_lines
from draftwitness.adapters.turnitin.ai import AiParsed, has_overview, parse_ai
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
from draftwitness.i18n import t

ADAPTER_NAME: Final = "turnitin-pdf"
ADAPTER_VERSION: Final = "0.1"
FEEDBACK_STUDIO: Final = "feedback_studio"
ENHANCED: Final = "enhanced"
AI_WRITING: Final = "ai_writing"
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
    r"(\d{1,2})-([^\W\d_]{3})-(\d{4}) (\d{1,2}):(\d{2})\s*([AaPp])\.?\s?[Mm]\.?\s*"
    r"\(UTC([+-])(\d{2}):?(\d{2})\)"
)
_ENHANCED_DATE = re.compile(
    r"([A-Za-z]{3}) (\d{1,2}), (\d{4}),? (\d{1,2}):(\d{2})\s*([AP]M)\s*"
    r"(?:GMT|UTC)(?:([+-])(\d{1,2})(?::?(\d{2}))?)?"
)
_ENHANCED_DATE_DMY = re.compile(
    r"(\d{1,2}) ([^\W\d_]{3})\.? (\d{4}),? (\d{1,2}):(\d{2})\s*([ap])\.?\s?m\.?\s*"
    r"(?:GMT|UTC)(?:([+-])(\d{1,2})(?::?(\d{2}))?)?"
)
_SUBMISSION_ID = re.compile(r"trn:oid:\S+")


@cache
def labels() -> dict[str, Any]:
    text = files("draftwitness.adapters.turnitin").joinpath("labels.yaml").read_text("utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    return data


def _languages(layout: str) -> dict[str, dict[str, Any]]:
    """The label sets of ``layout``, by language code."""
    return {key: value for key, value in labels()[layout].items() if isinstance(value, dict)}


def detect_layout(lines: list[str]) -> tuple[str, str] | None:
    """``(layout, language)`` of the first label set that matches, or ``None``. A PDF with
    a Similarity Report and an AI Writing Report is detected as its Similarity Report."""
    present = set(lines)
    for language, fs in _languages(FEEDBACK_STUDIO).items():
        if {fs["report_heading"], fs["overall"], fs["sources_heading"]} <= present:
            return FEEDBACK_STUDIO, language
    for language, en in _languages(ENHANCED).items():
        overall = any(line == en["overall"] or line.endswith(f" {en['overall']}") for line in lines)
        if overall and en["integrity_overview"] in {section for section, _ in _footers(lines, en)}:
            return ENHANCED, language
    ai_language = _ai_language(lines)
    return (AI_WRITING, ai_language) if ai_language else None


def _ai_words(language: str) -> dict[str, Any]:
    """The AI Writing Report's labels in ``language``, with the footer labels and cover
    section it shares with the enhanced Similarity Report."""
    shared = _languages(ENHANCED)[language]
    return {**_languages(AI_WRITING)[language], "skip_sections": [shared["cover_page"]]}


def _ai_footers(language: str) -> Callable[[list[str]], list[tuple[str, int]]]:
    words = _languages(ENHANCED)[language]
    return lambda lines: _footers(lines, words)


def _ai_language(lines: list[str]) -> str | None:
    """The language of the AI Writing Overview in ``lines``, if there is one."""
    for language in _languages(AI_WRITING).keys() & _languages(ENHANCED).keys():
        if has_overview(lines, _ai_words(language), _ai_footers(language)):
            return language
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


def parse_classic_date(text: str, months: list[str] | None = None) -> datetime | None:
    """``22-Sep-2023 04:02PM (UTC+0800)`` as an aware datetime; with the language's
    ``months``, also ``09-jun-2026 07:28p. m. (UTC+0100)``."""
    match = _CLASSIC_DATE.search(text)
    if match is None:
        return None
    name = match.group(2).lower()
    if name in _MONTHS:
        month = _MONTHS[name]
    elif months and name in months:
        month = months.index(name) + 1
    else:
        return None
    day, year = int(match.group(1)), int(match.group(3))
    hour, minute = _clock(match.group(4), match.group(5), match.group(6) + "M")
    try:
        return datetime(year, month, day, hour, minute, tzinfo=_offset(*match.group(7, 8, 9)))
    except ValueError:
        return None


def parse_enhanced_date(text: str, months: list[str] | None = None) -> datetime | None:
    """``Jul 11, 2026, 8:04 AM GMT+7`` as an aware datetime; with the language's ``months``,
    also ``29 ene 2025, 9:02 a.m. GMT-5``."""
    match = _ENHANCED_DATE.search(text)
    if match is not None and match.group(1).lower() in _MONTHS:
        month, day, year = _MONTHS[match.group(1).lower()], int(match.group(2)), int(match.group(3))
    elif months and (match := _ENHANCED_DATE_DMY.search(text)) and match.group(2).lower() in months:
        day, month, year = (
            int(match.group(1)),
            months.index(match.group(2).lower()) + 1,
            int(match.group(3)),
        )
    else:
        return None
    hour, minute = _clock(match.group(4), match.group(5), match.group(6)[0] + "M")
    zone = _offset(match.group(7), match.group(8), match.group(9))
    try:
        return datetime(year, month, day, hour, minute, tzinfo=zone)
    except ValueError:
        return None


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


def _labelled_percent(lines: list[str], label: str) -> tuple[float, bool] | None:
    """The percentage shown with ``label``: on the line before it, or at the start of its
    line ("23% Overall Similarity")."""
    for index, line in enumerate(lines):
        if line == label and index > 0 and (value := _percent(lines[index - 1])) is not None:
            return value
        if line.endswith(f" {label}") and (value := _percent(line[: -len(label)].strip())):
            return value
    return None


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


def _letters(text: str) -> str:
    return "".join(character for character in text.lower() if character.isalnum())


def _fs_title(lines: list[str], words: dict[str, Any]) -> str | None:
    """The submission title at the top of the cover, never the author name ("by …"). A
    title wrapped over several lines is kept as Turnitin prints it again, on one line, just
    above the report heading."""
    head = lines[:20]
    if len(head) > 1 and head[1].startswith(words["author_prefix"]):
        return head[0]
    fields = tuple(
        words[key] for key in ("author_prefix", "submission_date", "submission_id", "word_count")
    )
    end = next((i for i, line in enumerate(head) if line.startswith(fields)), 0)
    wrapped = _letters(" ".join(head[:end]))
    for index, line in enumerate(lines[1:], start=1):
        if line == words["report_heading"] and wrapped and _letters(lines[index - 1]) == wrapped:
            return lines[index - 1]
    return None


def _fs_submission(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    head = lines[:20]
    date_text = _after_prefix(head, words["submission_date"])
    submitted = parse_classic_date(date_text, words.get("months")) if date_text else None
    if date_text and submitted is None:
        parsed.warnings.append(t("adapters.warn_date"))
    word_count = _after_prefix(head, words["word_count"])
    characters = _after_prefix(head, words["character_count"])
    parsed.submission = Submission(
        title=_fs_title(lines, words),
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
                parsed.warnings.append(t("adapters.warn_source_no_name"))
            buffer = []
        elif line in skip or _RANK_ROW.match(line) or _PERCENT.match(line):
            continue
        elif not line.startswith(excludes):
            buffer.append(line)
    if buffer and buffer != [parsed.submission.title]:
        parsed.warnings.append(t("adapters.warn_text_after_sources"))
    return names


def _split_switches(lines: list[str], words: dict[str, Any]) -> list[str]:
    """The lines with each "Exclude …" switch on a line of its own: some reports print two
    on one line ("Excluir citas Apagado Excluir coincidencias Apagado")."""
    labels = (words["exclude_quotes"], words["exclude_bibliography"], words["exclude_matches"])
    starts = re.compile("(?=" + "|".join(map(re.escape, labels)) + ")")
    return [part.strip() for line in lines for part in starts.split(line) if part.strip()]


def _feedback_studio(lines: list[str], words: dict[str, Any]) -> _Parsed:
    parsed = _Parsed(product="Feedback Studio")
    _fs_submission(lines, words, parsed)
    starts = [i for i, line in enumerate(lines) if line == words["overall"]]
    report = _split_switches(lines[starts[-1] - 1 :], words)
    overall = _percent(report[0])
    parsed.overall = overall[0] if overall else None
    databases = {}
    for key in ("database_internet", "database_publications", "database_student_papers"):
        labels_ = words[key] if isinstance(words[key], list) else [words[key]]
        value = next((found for label in labels_ if (found := _value_before(report, label))), None)
        if value is not None:
            databases[key.removeprefix("database_")] = value[0]
    parsed.extensions["databases"] = databases
    parsed.filters = _fs_filters(report, words)

    ranks = _fs_ranks(report)
    names = _fs_names(report, words, parsed)
    if len(names) != len(ranks):
        parsed.warnings.append(
            t("adapters.warn_misaligned", percentages=len(ranks), names=len(names))
        )
    for rank, (label, kind) in enumerate(names, start=1):
        parsed.sources.append(_source(rank, label, kind, ranks.get(rank)))
    return parsed


# --- Enhanced Similarity Report -----------------------------------------------------------


def _footer(words: dict[str, Any]) -> re.Pattern[str]:
    pages = "|".join(map(re.escape, words["page_footer"]))
    of = "|".join(map(re.escape, words["page_of"]))
    return re.compile(rf"^(?:{pages}) \d+ (?:{of}) (\d+) - (.+)$")


def _footers(lines: list[str], words: dict[str, Any]) -> list[tuple[str, int]]:
    """``(section, pages)`` of each page footer such as "Page 2 of 13 - Integrity Overview"
    (the submission ID may follow on the same line)."""
    footer, label = _footer(words), f" {words['submission_id']}"
    found = []
    for line in lines:
        match = footer.match(line)
        if match:
            section = match.group(2)
            section = section.split(label)[0] if _SUBMISSION_ID.search(section) else section
            found.append((section.strip(), int(match.group(1))))
    return found


def _without_footers(lines: list[str], words: dict[str, Any]) -> list[str]:
    """The lines without the footer every page repeats: "Page 2 of 13 - Integrity Overview",
    then the submission ID on the same line or on the next one or two."""
    footer, label = _footer(words), words["submission_id"]
    kept: list[str] = []
    after_footer = False
    for line in lines:
        if footer.match(line):
            after_footer = True
        elif after_footer and (
            line == label or _SUBMISSION_ID.fullmatch(line.removeprefix(label).strip())
        ):
            continue
        else:
            after_footer = False
            kept.append(line)
    return kept


def _count(lines: list[str], suffixes: list[str]) -> int | None:
    for line in lines:
        for suffix in suffixes:
            match = re.match(rf"^([\d.,]+) {re.escape(suffix)}$", line, re.IGNORECASE)
            if match:
                return _number(match.group(1))
    return None


def _next_value(lines: list[str], label: str) -> str | None:
    for index, line in enumerate(lines[:-1]):
        if line == label:
            return lines[index + 1]
    return None


def _cover_title(before: list[str], file_name: str) -> str | None:
    """The title above "Document Details", only if it is the file name (Turnitin's default
    title), on one line or wrapped over two; the author name is never kept."""
    names = {file_name, file_name.rsplit(".", 1)[0]} - {""}
    for index, line in enumerate(before):
        if line in names:
            return line
        if index + 1 < len(before) and f"{line} {before[index + 1]}" in names:
            return f"{line} {before[index + 1]}"
    return None


def _enhanced_cover(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    try:
        details = lines.index(words["document_details"])
    except ValueError:
        parsed.warnings.append(t("adapters.warn_no_cover"))
        return
    cover = lines[details : details + 30]
    file_name = next(
        (value for label in words["file_name"] if (value := _next_value(cover, label))), ""
    )
    title = _cover_title(lines[max(0, details - 6) : details], file_name)
    if title is None:
        parsed.warnings.append(t("adapters.warn_title_dropped"))
    date_text = _next_value(cover, words["submission_date"])
    submitted = parse_enhanced_date(date_text, words["months"]) if date_text else None
    if date_text and submitted is None:
        parsed.warnings.append(t("adapters.warn_date"))
    parsed.submission = Submission(
        title=title,
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
    ends = {
        words["exclusions_heading"],
        words["match_groups_heading"],
        words["top_sources_heading"],
    }
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
                    parsed.warnings.append(t("adapters.warn_unchecked_filter", label=label))
                break
        else:
            parsed.warnings.append(t("adapters.warn_unknown_filter", item=item))
    parsed.filters = SimilarityFilters(
        quotes_excluded=found.get("quotes", False),
        bibliography_excluded=found.get("bibliography", False),
        small_matches_excluded=found.get("small_matches", False),
        small_matches_min_words=min_words,
    )
    parsed.extensions["cited_text_excluded"] = found.get("cited", False)


def _integrity_flags(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    """How many integrity flags the report raises (the Spanish reports print no number) and
    what it says about each, such as hidden text."""
    flags = _count(lines, [words["integrity_flags"]])
    if flags is not None:
        parsed.extensions["integrity_flags"] = flags
    if words["integrity_flags_heading"] not in lines:
        return
    start = lines.index(words["integrity_flags_heading"]) + 2
    stops = {words["top_sources_heading"], words["match_groups_heading"], words["overall"]}
    notes = []
    for line in lines[start : start + 12]:
        if line.startswith(words["integrity_flags_end"]) or line in stops:
            break
        if line != words["no_integrity_flags"]:
            notes.append(line)
    parsed.extensions["integrity_flag_notes"] = notes
    if notes:
        parsed.warnings.append(t("adapters.warn_integrity_flags", notes=" ".join(notes)))


def _enhanced_overview(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    overall = _labelled_percent(lines, words["overall"])
    parsed.overall = overall[0] if overall else None
    _enhanced_filters(lines, words, parsed)
    exclusions = _section(lines, words["exclusions_heading"], {words["match_groups_heading"]})
    for key in ("excluded_matches", "excluded_sources"):
        count = _count(exclusions, [words[key]])
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
        value = _labelled_percent(lines, label)
        if value is not None:
            databases[key] = value[0]
    parsed.extensions["databases"] = databases
    _integrity_flags(lines, words, parsed)


def _source_row(lines: list[str], index: int) -> tuple[str, list[str], tuple[float, bool]] | None:
    """The row starting at ``lines[index]`` (its rank): its kind line, its name lines and its
    percentage, which ends it within a few lines; or ``None``."""
    for end in range(index + 3, min(index + 7, len(lines))):
        value = _percent(lines[end])
        if value is not None:
            return lines[index + 1], lines[index + 2 : end], value
    return None


def _enhanced_sources(lines: list[str], words: dict[str, Any], parsed: _Parsed) -> None:
    """The Top Sources rows: rank, kind ("Internet", "Publication"…), name, percentage. Rows
    are numbered 1, 2, 3…, which is how the list is told apart from the paper after it."""
    intro = [i for i, line in enumerate(lines) if line.startswith(words["top_sources_intro"])]
    if not intro:
        return
    kinds: dict[str, str] = words["source_kinds"]
    index = intro[0] + 1
    truncated = False
    while index < len(lines) and lines[index] == str(len(parsed.sources) + 1):
        row = _source_row(lines, index)
        if row is None:
            break
        kind_label, name_lines, value = row
        if kind_label not in kinds:
            parsed.warnings.append(
                t("adapters.warn_unknown_source_kind", source=lines[index], kind=kind_label)
            )
        name = " ".join(name_lines)
        truncated = truncated or name.endswith(("...", "…"))
        kind = SourceKind(kinds.get(kind_label, "unknown"))
        parsed.sources.append(_source(len(parsed.sources) + 1, name or kind_label, kind, value))
        index += 2 + len(name_lines) + 1
    if truncated:
        parsed.warnings.append(t("adapters.warn_shortened_names"))
    if index < len(lines) and lines[index].isdigit() and _source_row(lines, index):
        parsed.warnings.append(t("adapters.warn_rank_gap"))
    if not parsed.sources:
        parsed.warnings.append(t("adapters.warn_unreadable_source_list"))


def _enhanced(lines: list[str], words: dict[str, Any]) -> _Parsed:
    parsed = _Parsed(product="Similarity Report")
    footers = _footers(lines, words)
    text = " ".join(lines)  # the footers carry the submission ID when the cover is missing
    lines = _without_footers(lines, words)
    _enhanced_cover(lines, words, parsed)
    _enhanced_overview(lines, words, parsed)
    _enhanced_sources(lines, words, parsed)
    if parsed.submission.submission_id is None and (found := _SUBMISSION_ID.search(text)):
        parsed.submission = parsed.submission.model_copy(update={"submission_id": found.group(0)})
    parsed.extensions["sections"] = list(dict.fromkeys(section for section, _ in footers))
    if footers:
        parsed.extensions["report_pages"] = footers[0][1]
    return parsed


# --- Report -------------------------------------------------------------------------------


def _check(parsed: _Parsed) -> None:
    if parsed.overall is None:
        return
    for source in parsed.sources:
        if source.percent is not None and source.percent > parsed.overall:
            parsed.warnings.append(
                t(
                    "adapters.warn_source_above",
                    source=source.rank,
                    percent=f"{source.percent:g}",
                    ceiling=t("adapters.ceiling_overall", percent=f"{parsed.overall:g}"),
                )
            )


def _ai_cover(lines: list[str], language: str) -> _Parsed:
    """The submission details of an AI Writing Report downloaded on its own: its cover page
    has the same labels as the enhanced Similarity Report's."""
    parsed = _Parsed(product="AI Writing Report")
    words = _languages(ENHANCED)[language]
    footers = _footers(lines, words)
    _enhanced_cover(_without_footers(lines, words), words, parsed)
    if parsed.submission.submission_id is None and (
        found := _SUBMISSION_ID.search(" ".join(lines))
    ):
        parsed.submission = parsed.submission.model_copy(update={"submission_id": found.group(0)})
    parsed.extensions["sections"] = list(dict.fromkeys(section for section, _ in footers))
    return parsed


def _read_ai(data: bytes, lines: list[str], language: str) -> AiParsed:
    colour = tuple(float(c) for c in labels()[AI_WRITING]["ai_generated_colour"])
    return parse_ai(open_pdf(data), lines, _ai_words(language), _ai_footers(language), colour)


def _kind(parsed: _Parsed | None, ai: AiParsed | None) -> tuple[ReportKind, str]:
    if parsed is None:
        return ReportKind.AI_WRITING, "AI Writing Report"
    if ai is None:
        return ReportKind.SIMILARITY, parsed.product
    return ReportKind.COMBINED, f"{parsed.product} + AI Writing Report"


def parse_pdf(
    data: bytes,
    filename: str,
    sha256: str,
    *,
    parsed_at: datetime,
    lines: list[str] | None = None,
) -> Report:
    """Turn a downloaded Turnitin PDF report into a :class:`Report`. ``lines`` are the
    report's :func:`~draftwitness.adapters.pdftext.pdf_lines`, if already extracted."""
    lines = pdf_lines(data) if lines is None else lines
    detected = detect_layout(lines)
    if detected is None:
        raise AdapterError(
            t("adapters.not_turnitin", languages=", ".join(sorted(_languages(ENHANCED))))
        )
    layout, language = detected
    similarity: _Parsed | None = None
    if layout == AI_WRITING:
        details = _ai_cover(lines, language)
        ai_language: str | None = language
    else:
        parse = _feedback_studio if layout == FEEDBACK_STUDIO else _enhanced
        similarity = details = parse(lines, _languages(layout)[language])
        if similarity.overall is None:
            raise AdapterError("the overall similarity percentage could not be read")
        _check(similarity)
        similarity.warnings.append(t("adapters.warn_turnitin_highlights"))
        unreadable = t("adapters.warn_unreadable_source_list")
        if not similarity.sources and unreadable not in similarity.warnings:
            similarity.warnings.append(t("adapters.warn_no_source_list"))
        ai_language = _ai_language(lines) if layout == ENHANCED else None
    ai = _read_ai(data, lines, ai_language) if ai_language else None
    warnings = [*details.warnings, *(ai.warnings if ai else [])]
    page_totals = [
        pages
        for pages in (details.extensions.get("report_pages"), ai and ai.extensions["report_pages"])
        if isinstance(pages, int)
    ]
    pdf_pages = len(open_pdf(data).pages)
    if page_totals and sum(page_totals) > pdf_pages:
        warnings.append(t("adapters.warn_extract", report=sum(page_totals), pdf=pdf_pages))
    turnitin: dict[str, Any] = {"layout": layout, "language": language, **details.extensions}
    if ai is not None:
        turnitin["ai_writing"] = {"language": ai_language, **ai.extensions}
    kind, product = _kind(similarity, ai)
    return Report(
        tool=Tool(name="turnitin", product=product, report_kind=kind),
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
        submission=details.submission,
        similarity=(
            Similarity(
                overall_percent=similarity.overall,
                filters=similarity.filters,
                sources=similarity.sources,
            )
            if similarity is not None and similarity.overall is not None
            else None
        ),
        ai_writing=ai.ai_writing if ai else None,
        warnings=warnings,
        extensions={"turnitin": turnitin},
    )
