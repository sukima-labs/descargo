"""Inspect a PDF: Info and XMP metadata, incremental updates, attachments, invisible text."""

import io
from dataclasses import dataclass, field
from typing import Any, Final
from xml.etree.ElementTree import Element

from pypdf import PasswordType, PdfReader
from pypdf.errors import DependencyError, PdfReadError

from draftwitness.core.documents.archive import MAX_MEMBER_BYTES, DocumentError, parse_xml
from draftwitness.modules.pre.inspect.chars import Segment
from draftwitness.modules.pre.inspect.common import (
    FormatResult,
    Passages,
    metadata_field,
    qualified,
)
from draftwitness.modules.pre.inspect.models import Finding, FindingKind, Level, Location

RDF: Final = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
INVISIBLE_MODES: Final = frozenset({3, 7})
"""Text render modes that paint nothing: 3 (invisible) and 7 (clip only)."""
FILL_MODES: Final = frozenset({0, 2, 4, 6})
_SHOW: Final = frozenset({b"Tj", b"TJ", b"'", b'"'})
_LINEARIZED_WINDOW: Final = 2048


def _is_white(operands: list[Any]) -> bool:
    try:
        values = [float(v) for v in operands]
    except (TypeError, ValueError):
        return False
    if len(values) in {1, 3}:
        return all(v >= 1 for v in values)
    if len(values) == 4:
        return all(v <= 0 for v in values)
    return False


@dataclass
class _TextState:
    """Follows the render mode and fill colour while pypdf extracts a page's text.

    pypdf reports text in chunks, so a chunk is attributed to invisible or white text when
    any text in it was shown in that state (ADR 006: neighbouring text may be included).
    """

    location: Location
    invisible: Passages
    white: Passages
    mode: int = 0
    fill_white: bool = False
    stack: list[tuple[int, bool]] = field(default_factory=list)
    pending_invisible: bool = False
    pending_white: bool = False

    def before(self, operator: bytes, operands: list[Any], _cm: object, _tm: object) -> None:
        if operator == b"q":
            self.stack.append((self.mode, self.fill_white))
        elif operator == b"Q" and self.stack:
            self.mode, self.fill_white = self.stack.pop()
        elif operator == b"Tr" and operands:
            try:
                self.mode = int(operands[0])
            except (TypeError, ValueError):
                self.mode = 0
        elif operator in {b"g", b"rg", b"k", b"sc", b"scn"}:
            self.fill_white = _is_white(operands)
        elif operator == b"cs":
            self.fill_white = False
        elif operator in _SHOW:
            if self.mode in INVISIBLE_MODES:
                self.pending_invisible = True
            elif self.fill_white and self.mode in FILL_MODES:
                self.pending_white = True

    def text(self, text: str, _cm: object, _tm: object, _font: object, _size: object) -> None:
        if not text.strip():
            return
        if self.pending_invisible:
            self.invisible.add(self.location, text)
        elif self.pending_white:
            self.white.add(self.location, text)
        self.pending_invisible = self.pending_white = False


def _info(reader: PdfReader, result: FormatResult) -> None:
    info = reader.metadata
    if info is None:
        return
    for key in info:
        value = info[key]
        shown = value.get_object() if hasattr(value, "get_object") else value
        result.metadata.append(metadata_field("Info", str(key).lstrip("/"), str(shown)))


def _xmp_value(element: Element) -> str:
    items = list(element.iter(f"{RDF}li"))
    if items:
        texts = [item.text.strip() for item in items if item.text and item.text.strip()]
        return "; ".join(texts) if texts else f"{len(items)} entries"
    return (element.text or "").strip()


def _xmp(reader: PdfReader, result: FormatResult) -> None:
    root = reader.trailer.get("/Root")
    metadata = root.get_object().get("/Metadata") if root is not None else None
    if metadata is None:
        return
    stream = metadata.get_object()
    data = stream.get_data()
    if len(data) > MAX_MEMBER_BYTES:
        result.notes.append("xmp_too_large")
        return
    try:
        xmp = parse_xml(data, "XMP")
    except DocumentError:
        result.notes.append("xmp_unreadable")
        return
    for description in xmp.iter(f"{RDF}Description"):
        for key, value in description.attrib.items():
            if not key.startswith(RDF) and value.strip():
                result.metadata.append(metadata_field("XMP", qualified(key), value))
        for child in description:
            value = _xmp_value(child)
            if value:
                result.metadata.append(metadata_field("XMP", qualified(child.tag), value))


def _updates(data: bytes, result: FormatResult) -> None:
    markers = data.count(b"%%EOF")
    linearized = b"/Linearized" in data[:_LINEARIZED_WINDOW]
    updates = markers - (2 if linearized else 1)
    if updates > 0:
        result.add(
            Finding(
                kind=FindingKind.INCREMENTAL_UPDATES,
                level=Level.REVIEW,
                count=updates,
                details={"eof_markers": markers, "linearized": "yes" if linearized else "no"},
            )
        )


def _attachments(reader: PdfReader, result: FormatResult) -> None:
    try:
        attachments = reader.attachments
        names = sorted(attachments)
    except (PdfReadError, KeyError, TypeError, AttributeError):
        result.notes.append("attachments_unreadable")
        return
    if names:
        result.add(
            Finding(
                kind=FindingKind.ATTACHMENTS,
                level=Level.REVIEW,
                count=len(names),
                details={"names": ", ".join(names)},
            )
        )


def _open(data: bytes, result: FormatResult) -> PdfReader | None:
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise DocumentError(f"cannot read PDF: {exc}") from exc
    if not reader.is_encrypted:
        return reader
    try:
        opened = reader.decrypt("") is not PasswordType.NOT_DECRYPTED
    except (DependencyError, NotImplementedError, PdfReadError):
        opened = False
    result.add(
        Finding(
            kind=FindingKind.ENCRYPTED,
            level=Level.REVIEW,
            count=1,
            details={"opened_without_password": "yes" if opened else "no"},
        )
    )
    if not opened:
        result.notes.append("pdf_locked")
        return None
    return reader


def inspect_pdf(data: bytes) -> FormatResult:
    result = FormatResult()
    _updates(data, result)
    reader = _open(data, result)
    if reader is None:
        return result
    try:
        _info(reader, result)
        _xmp(reader, result)
        _attachments(reader, result)
        invisible, white = Passages(), Passages()
        for number, page in enumerate(reader.pages, start=1):
            state = _TextState(Location(page=number), invisible, white)
            text = page.extract_text(visitor_operand_before=state.before, visitor_text=state.text)
            result.segments.append(Segment(Location(page=number), text or ""))
    except PdfReadError as exc:
        raise DocumentError(f"cannot read PDF: {exc}") from exc
    result.add(invisible.finding(FindingKind.INVISIBLE_TEXT, Level.REVIEW))
    result.add(white.finding(FindingKind.WHITE_TEXT, Level.REVIEW))
    return result
