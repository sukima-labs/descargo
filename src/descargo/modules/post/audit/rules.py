"""Span-level rules of the similarity auditor: reference lists, quotations, citations.

Each rule is a separate function that reports *what it found* (the heading, the quotation
marks, the citation), so the auditor can show its evidence. Patterns come from
``rules.yaml`` (ADR 005), not from code.
"""

import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Final

import regex
import yaml
from pydantic import BaseModel, ConfigDict, Field

from descargo.core.documents import TextDocument
from descargo.core.documents.text import PARAGRAPH_SEPARATOR

_HEADING_DECORATION: Final = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*)?(?:(?:\d+(?:\.\d+)*|[IVXLC]+)[.)]?\s+)?(.*?)(?:\*\*)?\s*[:.]?\s*$"
)
_MAX_HEADING_WORDS: Final = 6


class _CitationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    example: str
    pattern: str


class _RulesFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_headings: list[str] = Field(min_length=1)
    section_end_headings: list[str] = []
    quote_pairs: list[tuple[str, str]] = Field(min_length=1)
    citation_window: int = Field(ge=1)
    citations: list[_CitationSpec] = Field(min_length=1)


@dataclass(frozen=True)
class CitationPattern:
    name: str
    pattern: regex.Pattern[str]


@dataclass(frozen=True)
class AuditRules:
    reference_headings: frozenset[str]
    section_end_headings: frozenset[str]
    quote_pairs: tuple[tuple[str, str], ...]
    citation_window: int
    citations: tuple[CitationPattern, ...]

    @property
    def quote_chars(self) -> frozenset[str]:
        return frozenset(char for pair in self.quote_pairs for char in pair)


def load_rules(path: Path | None = None) -> AuditRules:
    """Load patterns from ``path``, or the bundled ``rules.yaml``."""
    if path is None:
        return _bundled_rules()
    return _rules_from_text(path.read_text("utf-8"))


@cache
def _bundled_rules() -> AuditRules:
    text = files("descargo.modules.post.audit").joinpath("rules.yaml").read_text("utf-8")
    return _rules_from_text(text)


def _rules_from_text(text: str) -> AuditRules:
    data = _RulesFile.model_validate(yaml.safe_load(text))
    return AuditRules(
        reference_headings=frozenset(h.casefold() for h in data.reference_headings),
        section_end_headings=frozenset(h.casefold() for h in data.section_end_headings),
        quote_pairs=tuple(data.quote_pairs),
        citation_window=data.citation_window,
        citations=tuple(CitationPattern(c.name, regex.compile(c.pattern)) for c in data.citations),
    )


# --- Reference list ------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    start: int
    end: int
    heading: str


def _heading_key(line: str) -> str | None:
    match = _HEADING_DECORATION.match(line)
    if match is None:  # pragma: no cover - the pattern matches any single line
        return None
    key = " ".join(match.group(1).split()).casefold()
    if not key or len(key.split()) > _MAX_HEADING_WORDS:
        return None
    return key


def _lines(text: str, start: int, end: int) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    offset = start
    for line in text[start:end].split("\n"):
        lines.append((offset, line))
        offset += len(line) + 1
    return lines


def bibliography_section(document: TextDocument, rules: AuditRules) -> Section | None:
    """The reference list: from the last reference heading in the body to the next
    appendix heading, or to the end of the body."""
    lines = _lines(document.text, 0, document.body_end)
    found: tuple[int, int, str] | None = None
    for index, (offset, line) in enumerate(lines):
        if _heading_key(line) in rules.reference_headings:
            found = (index, offset, line.strip().lstrip("#").strip())
    if found is None:
        return None
    index, offset, heading = found
    end = document.body_end
    for later_offset, line in lines[index + 1 :]:
        if _heading_key(line) in rules.section_end_headings:
            end = later_offset
            break
    return Section(start=offset, end=end, heading=heading)


# --- Quotations ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Quotation:
    start: int
    """Offset of the opening mark (or of the block quotation)."""
    end: int
    """Offset just after the closing mark (or the end of the block quotation)."""
    marks: str
    """The marks found, e.g. ``“…”``, or ``block`` for a block quotation."""


def _is_mark(text: str, index: int) -> bool:
    """A quote character between two letters or digits is an apostrophe."""
    before = text[index - 1] if index > 0 else " "
    after = text[index + 1] if index + 1 < len(text) else " "
    return not (before.isalnum() and after.isalnum())


def _marks(text: str, char: str, start: int, end: int) -> list[int]:
    return [i for i in range(start, end) if text[i] == char and _is_mark(text, i)]


def enclosing_quotation(
    document: TextDocument, start: int, end: int, rules: AuditRules
) -> Quotation | None:
    """The quotation that contains the whole span ``[start, end)``, if any."""
    paragraph = document.paragraph_at(start)
    if paragraph is None:
        return None
    if paragraph.quote:
        return Quotation(paragraph.start, paragraph.end, "block")
    text = document.text
    trim = rules.quote_chars | {".", ",", ";", ":"}
    while start < end and (text[start].isspace() or text[start] in rules.quote_chars):
        start += 1
    while end > start and (text[end - 1].isspace() or text[end - 1] in trim):
        end -= 1
    for opening, closing in rules.quote_pairs:
        before = _marks(text, opening, paragraph.start, start)
        if not before:
            continue
        if opening == closing:
            if len(before) % 2 == 0:
                continue
        elif _marks(text, closing, before[-1] + 1, start):
            continue
        if _marks(text, closing, start, end):
            continue
        after = _marks(text, closing, end, paragraph.end)
        if after:
            return Quotation(before[-1], after[0] + 1, f"{opening}…{closing}")
    return None


# --- Citations -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Citation:
    text: str
    start: int
    style: str


def _first_citation(text: str, offset: int, rules: AuditRules) -> Citation | None:
    found: list[Citation] = []
    for spec in rules.citations:
        match = spec.pattern.search(text)
        if match:
            found.append(Citation(match.group(0), offset + match.start(), spec.name))
    return min(found, key=lambda c: c.start) if found else None


def _last_citation(text: str, offset: int, rules: AuditRules) -> Citation | None:
    found: list[tuple[int, Citation]] = []
    for spec in rules.citations:
        for match in spec.pattern.finditer(text):
            found.append((match.end(), Citation(match.group(0), offset + match.start(), spec.name)))
    return max(found, key=lambda item: item[0])[1] if found else None


def citation_near(
    document: TextDocument, start: int, end: int, rules: AuditRules
) -> Citation | None:
    """A citation marker just after ``[start, end)`` or, failing that, just before it.

    The search stays within the paragraph, except that a block quotation's citation may
    open the following paragraph. Note references in the document count as citations.
    """
    paragraph = document.paragraph_at(start)
    if paragraph is None:
        return None
    window = rules.citation_window
    limit = paragraph.end
    if paragraph.quote:
        limit = paragraph.end + len(PARAGRAPH_SEPARATOR) + window
    after_end = min(end + window, limit, len(document.text))
    for mark in document.citation_marks:
        if end <= mark <= after_end:
            return Citation("", mark, "note_reference")
    after = _first_citation(document.text[end:after_end], end, rules)
    if after is not None:
        return after
    before_start = max(paragraph.start, start - window)
    return _last_citation(document.text[before_start:start], before_start, rules)
