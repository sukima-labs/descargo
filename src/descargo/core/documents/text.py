"""Extract a plain-text view of a document, keeping the structure the auditor needs.

Files are only read, never written. The view keeps paragraph boundaries, which paragraphs
are block quotations, where footnote or endnote references sit (they count as citation
markers) and where the body ends (notes are appended after it).

Archive members are read through :mod:`descargo.core.documents.archive`, which
size-checks them and parses XML with defusedxml.
"""

import bisect
import io
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Element

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from descargo.core.documents.archive import DocumentError, parse_xml, read_member

PARAGRAPH_SEPARATOR: Final = "\n\n"
TEXT_SUFFIXES: Final = frozenset({".txt", ".text", ".md", ".markdown"})
_WORD = re.compile(r"[^\W_]+(?:['\u2019-][^\W_]+)*")
_BLANK_LINES = re.compile(r"\n[ \t]*\n+")
_QUOTE_PREFIX = re.compile(r"^[ \t]*> ?", re.MULTILINE)
_MARKER_TEXT = re.compile(r"^[\s\d,;\-\u2013*\u2020\u2021\[\]()]+$")


def count_words(text: str) -> int:
    """Count words the way the auditor does: letter/digit runs, keeping hyphens and
    apostrophes inside words. Detectors count slightly differently."""
    return sum(1 for _ in _WORD.finditer(text))


@dataclass(frozen=True)
class Paragraph:
    start: int
    end: int
    quote: bool = False
    """A block quotation, by paragraph style or a Markdown ``>`` prefix."""
    note: bool = False
    """Footnote or endnote text, appended after the body."""


@dataclass(frozen=True)
class TextDocument:
    text: str
    paragraphs: tuple[Paragraph, ...]
    citation_marks: tuple[int, ...]
    """Offsets of note references and superscript markers in ``text``."""
    body_end: int
    source_format: str
    _starts: tuple[int, ...] = field(default=(), repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_starts", tuple(p.start for p in self.paragraphs))

    @property
    def word_count(self) -> int:
        return count_words(self.text)

    def paragraph_at(self, offset: int) -> Paragraph | None:
        index = bisect.bisect_right(self._starts, offset) - 1
        if index >= 0 and offset <= self.paragraphs[index].end:
            return self.paragraphs[index]
        return None


@dataclass
class _Para:
    text: str = ""
    quote: bool = False
    note: bool = False
    marks: list[int] = field(default_factory=list)


class _Builder:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.length = 0
        self.paragraphs: list[Paragraph] = []
        self.marks: list[int] = []
        self.body_end: int | None = None

    def add(self, para: _Para) -> None:
        if not para.text.strip():
            return
        if self.parts:
            self.parts.append(PARAGRAPH_SEPARATOR)
            self.length += len(PARAGRAPH_SEPARATOR)
        start = self.length
        self.parts.append(para.text)
        self.length += len(para.text)
        self.paragraphs.append(Paragraph(start, self.length, para.quote, para.note))
        self.marks.extend(start + mark for mark in para.marks)

    def end_body(self) -> None:
        self.body_end = self.length

    def build(self, source_format: str) -> TextDocument:
        return TextDocument(
            text="".join(self.parts),
            paragraphs=tuple(self.paragraphs),
            citation_marks=tuple(sorted(self.marks)),
            body_end=self.length if self.body_end is None else self.body_end,
            source_format=source_format,
        )


def text_document(text: str) -> TextDocument:
    """Build a view of plain text or Markdown. Blank lines separate paragraphs, and a
    paragraph whose every line starts with ``>`` is a block quotation."""
    builder = _Builder()
    for chunk in _BLANK_LINES.split(text.replace("\r\n", "\n")):
        lines = [line for line in chunk.split("\n") if line.strip()]
        quote = bool(lines) and all(line.lstrip().startswith(">") for line in lines)
        builder.add(_Para(_QUOTE_PREFIX.sub("", chunk) if quote else chunk, quote=quote))
    return builder.build("text")


# --- OOXML (DOCX) -------------------------------------------------------------------------

_W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC_FALLBACK: Final = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
_QUOTE_STYLE = re.compile(r"quot|cita", re.IGNORECASE)


def _docx_run_is_superscript(run: Element) -> bool:
    props = run.find(f"{_W}rPr")
    align = props.find(f"{_W}vertAlign") if props is not None else None
    return align is not None and align.get(f"{_W}val") == "superscript"


def _docx_collect(element: Element, para: _Para, nested: list[_Para]) -> None:
    for child in element:
        tag = child.tag
        if tag == _MC_FALLBACK:
            continue
        if tag == f"{_W}p":
            inner = _Para()
            _docx_collect(child, inner, nested)
            nested.append(inner)
        elif tag == f"{_W}t":
            para.text += child.text or ""
        elif tag == f"{_W}tab":
            para.text += "\t"
        elif tag in {f"{_W}br", f"{_W}cr"}:
            para.text += "\n"
        elif tag in {f"{_W}footnoteReference", f"{_W}endnoteReference"}:
            para.marks.append(len(para.text))
        elif tag == f"{_W}pStyle":
            para.quote = bool(_QUOTE_STYLE.search(child.get(f"{_W}val", "")))
        elif tag == f"{_W}r":
            before = len(para.text)
            _docx_collect(child, para, nested)
            if _docx_run_is_superscript(child) and _MARKER_TEXT.match(para.text[before:]):
                para.marks.append(before)
        else:
            _docx_collect(child, para, nested)


def _docx_paragraphs(root: Element, *, note: bool = False) -> Iterator[_Para]:
    for child in root:
        if child.tag == _MC_FALLBACK:
            continue
        if child.tag == f"{_W}p":
            para = _Para(note=note)
            nested: list[_Para] = []
            _docx_collect(child, para, nested)
            yield para
            for inner in nested:
                inner.note = note
                yield inner
        elif child.tag in {f"{_W}footnote", f"{_W}endnote"} and child.get(f"{_W}type") in {
            "separator",
            "continuationSeparator",
            "continuationNotice",
        }:
            continue
        else:
            yield from _docx_paragraphs(child, note=note)


def _docx(data: bytes) -> TextDocument:
    builder = _Builder()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        body = read_member(archive, "word/document.xml")
        if body is None:
            raise DocumentError("not a DOCX file: word/document.xml is missing")
        for para in _docx_paragraphs(parse_xml(body, "word/document.xml")):
            builder.add(para)
        builder.end_body()
        for part in ("word/footnotes.xml", "word/endnotes.xml"):
            notes = read_member(archive, part)
            if notes is not None:
                for para in _docx_paragraphs(parse_xml(notes, part), note=True):
                    builder.add(para)
    return builder.build("docx")


# --- ODF (ODT) ----------------------------------------------------------------------------

_TEXT: Final = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_OFFICE: Final = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_STYLE: Final = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"


@dataclass(frozen=True)
class _OdfStyles:
    quote: frozenset[str]
    superscript: frozenset[str]

    @classmethod
    def read(cls, *roots: Element) -> "_OdfStyles":
        quote: set[str] = set()
        superscript: set[str] = set()
        for root in roots:
            for style in root.iter(f"{_STYLE}style"):
                name = style.get(f"{_STYLE}name", "")
                parent = style.get(f"{_STYLE}parent-style-name", "")
                if _QUOTE_STYLE.search(name) or _QUOTE_STYLE.search(parent):
                    quote.add(name)
                props = style.find(f"{_STYLE}text-properties")
                position = props.get(f"{_STYLE}text-position", "") if props is not None else ""
                if position.startswith("super"):
                    superscript.add(name)
        return cls(frozenset(quote), frozenset(superscript))


def _odf_collect(element: Element, para: _Para, notes: list[_Para], styles: _OdfStyles) -> None:
    para.text += element.text or ""
    for child in element:
        tag = child.tag
        if tag == f"{_TEXT}s":
            para.text += " " * int(child.get(f"{_TEXT}c", "1"))
        elif tag == f"{_TEXT}tab":
            para.text += "\t"
        elif tag == f"{_TEXT}line-break":
            para.text += "\n"
        elif tag == f"{_TEXT}note":
            para.marks.append(len(para.text))
            body = child.find(f"{_TEXT}note-body")
            if body is not None:
                notes.extend(_odf_paragraphs(body, styles, note=True))
        elif tag in {f"{_OFFICE}annotation", f"{_OFFICE}annotation-end"}:
            pass
        else:
            before = len(para.text)
            _odf_collect(child, para, notes, styles)
            superscript = child.get(f"{_TEXT}style-name", "") in styles.superscript
            if superscript and _MARKER_TEXT.match(para.text[before:]):
                para.marks.append(before)
        para.text += child.tail or ""


def _odf_paragraphs(root: Element, styles: _OdfStyles, *, note: bool = False) -> Iterator[_Para]:
    for child in root:
        if child.tag in {f"{_TEXT}p", f"{_TEXT}h"}:
            quote = child.get(f"{_TEXT}style-name", "") in styles.quote
            para = _Para(quote=quote, note=note)
            notes: list[_Para] = []
            _odf_collect(child, para, notes, styles)
            yield para
            yield from notes
        elif child.tag != f"{_TEXT}tracked-changes":
            yield from _odf_paragraphs(child, styles, note=note)


def _odt(data: bytes) -> TextDocument:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        content = read_member(archive, "content.xml")
        if content is None:
            raise DocumentError("not an ODT file: content.xml is missing")
        root = parse_xml(content, "content.xml")
        styles_xml = read_member(archive, "styles.xml")
        style_roots = [root] + ([parse_xml(styles_xml, "styles.xml")] if styles_xml else [])
    styles = _OdfStyles.read(*style_roots)
    body = root.find(f"{_OFFICE}body")
    body_paragraphs: list[_Para] = []
    note_paragraphs: list[_Para] = []
    for para in _odf_paragraphs(body if body is not None else root, styles):
        (note_paragraphs if para.note else body_paragraphs).append(para)
    builder = _Builder()
    for para in body_paragraphs:
        builder.add(para)
    builder.end_body()
    for para in note_paragraphs:
        builder.add(para)
    return builder.build("odt")


# --- PDF ----------------------------------------------------------------------------------


def _pdf_pages(data: bytes) -> Iterable[str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentError("the PDF is encrypted")
        return [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise DocumentError(f"cannot read PDF: {exc}") from exc


def _pdf(data: bytes) -> TextDocument:
    builder = _Builder()
    for page in _pdf_pages(data):
        for chunk in _BLANK_LINES.split(page):
            builder.add(_Para(chunk))
    return builder.build("pdf")


def extract_text(path: Path) -> TextDocument:
    """Read ``path`` (.txt, .md, .docx, .odt or .pdf) without modifying it."""
    suffix = path.suffix.lower()
    data = path.read_bytes()
    try:
        if suffix in TEXT_SUFFIXES:
            return text_document(data.decode("utf-8-sig"))
        if suffix == ".docx":
            return _docx(data)
        if suffix == ".odt":
            return _odt(data)
        if suffix == ".pdf":
            return _pdf(data)
    except (zipfile.BadZipFile, UnicodeDecodeError) as exc:
        raise DocumentError(f"{path.name}: {exc}") from exc
    raise DocumentError(f"unsupported document type {suffix!r}; use .txt, .md, .docx, .odt or .pdf")
