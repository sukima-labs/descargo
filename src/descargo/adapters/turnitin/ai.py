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
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

from pypdf import PageObject, PdfReader
from pypdf.errors import PdfReadError

from descargo.adapters.base import AdapterError
from descargo.adapters.pdftext import normalized_lines
from descargo.core.report_schema import AiSegment, AiWriting
from descargo.i18n import t

#: How far a fill colour may be from the expected one.
_TOLERANCE: Final = 0.02
#: A baseline counts as on a highlight when it lies this far above the rectangle's bottom
#: edge at most, or slightly below it.
_BASELINE_BELOW: Final = 1.5
_BASELINE_ABOVE: Final = 5.0
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


@dataclass
class _Piece:
    x: float
    y: float
    text: str


@dataclass
class _Page:
    """One page: its text lines, its pieces of text with their positions, and the
    shapes filled in the AI colour, as boxes."""

    number: int
    colour: tuple[float, ...]
    lines: list[str] = field(default_factory=list)
    pieces: list[_Piece] = field(default_factory=list)
    rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    _fill: tuple[float, ...] | None = None
    _path: list[list[tuple[float, float]]] = field(default_factory=list)
    """The current path, as the points of each subpath."""

    def before(self, operator: bytes, operands: list[Any], cm: list[float], _tm: object) -> None:
        if operator in {b"rg", b"sc", b"scn"}:
            self._fill = tuple(float(o) for o in operands if isinstance(o, int | float)) or None
        elif operator == b"re" and len(operands) == 4:
            x, y, w, h = (float(o) for o in operands)
            self._path += [[_apply(cm, x, y), _apply(cm, x + w, y + h)]]
        elif operator == b"m" and len(operands) == 2:
            self._path.append([_apply(cm, float(operands[0]), float(operands[1]))])
        elif operator == b"l" and len(operands) == 2 and self._path:
            self._path[-1].append(_apply(cm, float(operands[0]), float(operands[1])))
        elif operator in {b"f", b"F", b"f*"}:
            if _same(self._fill, self.colour):
                self.rects += [_box(points) for points in self._path if len(points) > 1]
            self._path = []
        elif operator in {b"n", b"S", b"s", b"B", b"B*", b"b", b"b*"}:
            self._path = []

    def text(
        self, content: str, cm: list[float], tm: list[float], _font: object, _size: object
    ) -> None:
        x, y = _apply(cm, tm[4], tm[5])
        self.pieces.append(_Piece(x, y, unicodedata.normalize("NFKC", content)))

    def highlighted(self, piece: _Piece) -> bool:
        return any(
            left - 2 <= piece.x <= right
            and bottom - _BASELINE_BELOW <= piece.y <= bottom + _BASELINE_ABOVE
            for left, right, bottom, _top in self.rects
        )


def _apply(matrix: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def _box(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """``(left, right, bottom, top)`` around ``points``: Turnitin draws each highlight as a
    closed path of four points."""
    xs, ys = zip(*points, strict=True)
    return min(xs), max(xs), min(ys), max(ys)


def _same(colour: tuple[float, ...] | None, wanted: tuple[float, ...]) -> bool:
    return (
        colour is not None
        and len(colour) == len(wanted)
        and all(abs(a - b) <= _TOLERANCE for a, b in zip(colour, wanted, strict=True))
    )


def _read_page(page: PageObject, number: int, colour: tuple[float, ...]) -> _Page:
    drawn = _Page(number, colour)
    try:
        text = page.extract_text(visitor_operand_before=drawn.before, visitor_text=drawn.text)
    except PdfReadError as exc:
        raise AdapterError(t("adapters.unreadable_pdf", error=exc)) from exc
    drawn.lines = normalized_lines(text or "")
    return drawn


def _runs(page: _Page) -> list[str]:
    """Each run of highlighted text on ``page``, in reading order. A run ends at any text
    that is not highlighted."""
    runs: list[list[_Piece]] = [[]]
    for piece in page.pieces:
        if not piece.text.strip():
            if runs[-1]:
                runs[-1].append(piece)
        elif page.highlighted(piece):
            runs[-1].append(piece)
        elif runs[-1]:
            runs.append([])
    texts = []
    for run in runs:
        joined, last_y = "", None
        for piece in run:
            wrapped = last_y is not None and abs(piece.y - last_y) > 1
            if wrapped and joined and not joined[-1].isspace() and not piece.text[:1].isspace():
                joined += " "
            joined += piece.text.replace("\n", " ")
            last_y = piece.y
        text = " ".join(joined.split())
        if text:
            texts.append(text)
    return texts


def _segments(
    reader: PdfReader, words: dict[str, Any], footers: Footers, colour: tuple[float, ...]
) -> tuple[list[AiSegment], int, int | None]:
    """The highlighted passages on the AI Writing Report's own pages, the number of those
    pages that show the paper, and the report's page total."""
    pages = [_read_page(page, n, colour) for n, page in enumerate(reader.pages, start=1)]
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
            segments += [AiSegment(text=text, page=page.number) for text in _runs(page)]
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
