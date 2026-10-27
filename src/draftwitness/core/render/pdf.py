"""Render the small Markdown subset our templates use into a PDF.

Supported: ``#``/``##``/``###`` headings, paragraphs (consecutive lines are joined; a
trailing backslash forces a line break, as in CommonMark), ``-`` bullets (indented ones are
nested), ``1.`` numbered items, ``>`` quote blocks (which may contain ``-`` and nested
``  -`` bullets), ``---`` rules, inline ``**bold**`` and a ``<!-- pagebreak -->``
line (invisible in Markdown viewers). Anything else is printed as plain text, so nothing is
silently dropped.

Output is deterministic for a given input and ``created`` timestamp, so a third party can
regenerate the file and compare hashes.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Final

from fpdf import FPDF

from draftwitness import __version__

FONT_FAMILY: Final = "LiberationSerif"
_FONT_FILES: Final = {
    "": "LiberationSerif-Regular.ttf",
    "B": "LiberationSerif-Bold.ttf",
    "I": "LiberationSerif-Italic.ttf",
    "BI": "LiberationSerif-BoldItalic.ttf",
}
_BODY_SIZE: Final = 11
_LINE: Final = 5.5
_HEADING_SIZES: Final = {1: 16, 2: 13, 3: 11.5}
PAGE_BREAK: Final = "<!-- pagebreak -->"
_NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")


@dataclass(frozen=True)
class PdfMetadata:
    title: str
    language: str
    created: datetime
    subject: str | None = None


def _font_path(name: str) -> Path:
    return Path(str(files("draftwitness.core.render").joinpath("fonts", name)))


def _new_pdf(meta: PdfMetadata) -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_margins(left=22, top=20, right=22)
    pdf.set_auto_page_break(auto=True, margin=20)
    for style, filename in _FONT_FILES.items():
        pdf.add_font(FONT_FAMILY, style=style, fname=_font_path(filename))
    pdf.set_title(meta.title)
    pdf.set_lang(meta.language)
    if meta.subject:
        pdf.set_subject(meta.subject)
    pdf.set_creator(f"DraftWitness {__version__}")
    pdf.set_producer(f"DraftWitness {__version__}")
    pdf.set_creation_date(meta.created)
    pdf.add_page()
    pdf.set_font(FONT_FAMILY, size=_BODY_SIZE)
    return pdf


def _write_inline(pdf: FPDF, text: str, *, italic: bool = False) -> None:
    """Write text with ``**bold**`` spans, wrapping at the current margins."""
    base = "I" if italic else ""
    for index, part in enumerate(text.split("**")):
        if not part:
            continue
        bold = index % 2 == 1
        pdf.set_font(FONT_FAMILY, style=("B" if bold else "") + base, size=_BODY_SIZE)
        pdf.write(_LINE, part)
    pdf.set_font(FONT_FAMILY, size=_BODY_SIZE)
    pdf.ln(_LINE)


def _indented(pdf: FPDF, marker: str, text: str, indent: float, *, italic: bool = False) -> None:
    left = pdf.l_margin
    if marker:
        pdf.set_x(left + indent - 4)
        pdf.write(_LINE, marker)
    pdf.set_left_margin(left + indent)
    pdf.set_x(left + indent)
    _write_inline(pdf, text, italic=italic)
    pdf.set_left_margin(left)


def _quote_line(blocks: list[tuple[str, str]], text: str) -> None:
    if text.startswith("  - "):
        blocks.append(("qli2", text[4:]))
    elif text.startswith("- "):
        blocks.append(("qli", text[2:]))
    elif not text.strip():
        blocks.append(("qbreak", ""))
    elif blocks and blocks[-1][0] == "quote":
        blocks[-1] = ("quote", f"{blocks[-1][1]} {text.strip()}")
    else:
        blocks.append(("quote", text.strip()))


def _blocks(markdown: str) -> list[tuple[str, str]]:
    """Split Markdown into (kind, text) blocks."""
    blocks: list[tuple[str, str]] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            text = ""
            for part in paragraph:
                if text.endswith("\\"):
                    text = text[:-1] + "\n" + part
                else:
                    text = f"{text} {part}" if text else part
            blocks.append(("p", text.removesuffix("\\")))
            paragraph.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        numbered = _NUMBERED.match(line)
        if heading:
            flush()
            blocks.append((f"h{len(heading.group(1))}", heading.group(2)))
        elif line == "---":
            flush()
            blocks.append(("hr", ""))
        elif line == PAGE_BREAK:
            flush()
            blocks.append(("pagebreak", ""))
        elif line.startswith(("- ", "* ")):
            flush()
            blocks.append(("li2" if raw.startswith("  ") else "li", line[2:]))
        elif numbered:
            flush()
            blocks.append((f"ol{numbered.group(1)}", numbered.group(2)))
        elif line.startswith(">"):
            flush()
            _quote_line(blocks, line[1:].removeprefix(" "))
        elif blocks and blocks[-1][0] in {"li", "li2", "quote"} and raw.startswith("  "):
            kind, text = blocks[-1]
            blocks[-1] = (kind, f"{text} {line}")
        else:
            paragraph.append(line)
    flush()
    return blocks


_QUOTE_KINDS: Final = {"quote", "qli", "qli2", "qbreak"}
#: Indented kinds: (marker, indent in mm, space after).
_INDENTED: Final = {
    "li": ("\u2022", 7.0, 0.8),
    "li2": ("\u2013", 13.0, 0.5),
    "qli": ("\u2022", 10.0, 0.8),
    "qli2": ("\u2013", 15.0, 0.5),
    "quote": ("", 5.0, 0.5),
}


def _is_list(kind: str) -> bool:
    return kind in {"li", "li2", "qli", "qli2"} or kind.startswith("ol")


def _quote_bar(pdf: FPDF, start_page: int, start_y: float) -> None:
    """Grey bar left of a quote block (only when it did not cross a page break)."""
    if pdf.page == start_page:
        pdf.set_draw_color(170, 170, 170)
        pdf.set_line_width(0.6)
        pdf.line(pdf.l_margin + 1, start_y, pdf.l_margin + 1, pdf.get_y() - 1)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)


def _render_block(pdf: FPDF, kind: str, text: str) -> None:
    if kind in _INDENTED:
        marker, indent, after = _INDENTED[kind]
        _indented(pdf, marker, text, indent=indent)
        pdf.ln(after)
    elif kind.startswith("ol"):
        _indented(pdf, f"{kind[2:]}.", text, indent=8)
        pdf.ln(0.8)
    elif kind == "hr":
        y = pdf.get_y() + 2
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(5)
    elif kind == "qbreak":
        pdf.ln(1.5)
    elif kind == "pagebreak":
        pdf.add_page()
    elif kind.startswith("h"):
        pdf.ln(2)
        pdf.set_font(FONT_FAMILY, style="B", size=_HEADING_SIZES[int(kind[1])])
        pdf.multi_cell(0, _LINE + 1.5, text.replace("**", ""))
        pdf.set_font(FONT_FAMILY, size=_BODY_SIZE)
        pdf.ln(1)
    else:
        _write_inline(pdf, text)
        pdf.ln(2.5)


def render_pdf(markdown: str, meta: PdfMetadata) -> bytes:
    """Render ``markdown`` and return the PDF bytes."""
    pdf = _new_pdf(meta)
    quote_start: tuple[int, float] | None = None
    previous = ""
    for kind, text in _blocks(markdown):
        if kind in _QUOTE_KINDS and quote_start is None:
            quote_start = (pdf.page, pdf.get_y())
        elif kind not in _QUOTE_KINDS and quote_start is not None:
            _quote_bar(pdf, *quote_start)
            quote_start = None
            pdf.ln(2)
        if _is_list(previous) and not _is_list(kind):
            pdf.ln(1.5)
        previous = kind
        _render_block(pdf, kind, text)
    if quote_start is not None:
        _quote_bar(pdf, *quote_start)
    return bytes(pdf.output())
