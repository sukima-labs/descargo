"""Text drawn on filled rectangles in a downloaded PDF: how Turnitin and Copyleaks mark the
passages they attribute to AI, and how Copyleaks marks the passages that match a source.

:func:`read_page` collects a page's text pieces with their positions and the boxes filled
in the wanted colour; :func:`runs` joins the highlighted pieces into passages, in reading
order.
"""

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Final

from pypdf import PageObject
from pypdf.errors import PdfReadError

from descargo.adapters.base import AdapterError
from descargo.adapters.pdftext import normalized_lines
from descargo.i18n import t

#: How far a fill colour may be from the expected one.
TOLERANCE: Final = 0.02
#: A baseline counts as on a highlight when it lies this far above the rectangle's bottom
#: edge at most, or slightly below it.
BASELINE_BELOW: Final = 1.5
BASELINE_ABOVE: Final = 5.0


@dataclass
class Piece:
    x: float
    y: float
    text: str


@dataclass
class Page:
    """One page: its text lines, its pieces of text with their positions, and the
    shapes filled in the AI colour, as boxes."""

    number: int
    colour: tuple[float, ...]
    lines: list[str] = field(default_factory=list)
    pieces: list[Piece] = field(default_factory=list)
    rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    _fill: tuple[float, ...] | None = None
    _path: list[list[tuple[float, float]]] = field(default_factory=list)
    """The current path, as the points of each subpath."""

    def before(self, operator: bytes, operands: list[Any], cm: list[float], _tm: object) -> None:
        if operator in {b"rg", b"sc", b"scn"}:
            self._fill = tuple(float(o) for o in operands if isinstance(o, int | float)) or None
        elif operator == b"re" and len(operands) == 4:
            x, y, w, h = (float(o) for o in operands)
            self._path += [[apply(cm, x, y), apply(cm, x + w, y + h)]]
        elif operator == b"m" and len(operands) == 2:
            self._path.append([apply(cm, float(operands[0]), float(operands[1]))])
        elif operator == b"l" and len(operands) == 2 and self._path:
            self._path[-1].append(apply(cm, float(operands[0]), float(operands[1])))
        elif operator in {b"f", b"F", b"f*"}:
            if same(self._fill, self.colour):
                self.rects += [box(points) for points in self._path if len(points) > 1]
            self._path = []
        elif operator in {b"n", b"S", b"s", b"B", b"B*", b"b", b"b*"}:
            self._path = []

    def text(
        self, content: str, cm: list[float], tm: list[float], _font: object, _size: object
    ) -> None:
        x, y = apply(cm, tm[4], tm[5])
        self.pieces.append(Piece(x, y, unicodedata.normalize("NFKC", content)))

    def highlighted(self, piece: Piece) -> bool:
        return any(
            left - 2 <= piece.x <= right
            and bottom - BASELINE_BELOW <= piece.y <= bottom + BASELINE_ABOVE
            for left, right, bottom, _top in self.rects
        )


def apply(matrix: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def box(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """``(left, right, bottom, top)`` around ``points``: Turnitin draws each highlight as a
    closed path of four points."""
    xs, ys = zip(*points, strict=True)
    return min(xs), max(xs), min(ys), max(ys)


def same(colour: tuple[float, ...] | None, wanted: tuple[float, ...]) -> bool:
    return (
        colour is not None
        and len(colour) == len(wanted)
        and all(abs(a - b) <= TOLERANCE for a, b in zip(colour, wanted, strict=True))
    )


def read_page(page: PageObject, number: int, colour: tuple[float, ...]) -> Page:
    drawn = Page(number, colour)
    try:
        text = page.extract_text(visitor_operand_before=drawn.before, visitor_text=drawn.text)
    except PdfReadError as exc:
        raise AdapterError(t("adapters.unreadable_pdf", error=exc)) from exc
    drawn.lines = normalized_lines(text or "")
    return drawn


def runs(page: Page) -> list[str]:
    """Each run of highlighted text on ``page``, in reading order. A run ends at any text
    that is not highlighted."""
    runs: list[list[Piece]] = [[]]
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
