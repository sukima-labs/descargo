"""Run the inspector on a file's bytes and assemble an :class:`Inspection` (ADR 006)."""

import hashlib
import io
import unicodedata
import zipfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Final

from descargo.core.documents.archive import DocumentError
from descargo.modules.pre.inspect.chars import Segment, scan_characters
from descargo.modules.pre.inspect.common import FormatResult
from descargo.modules.pre.inspect.docx import inspect_docx
from descargo.modules.pre.inspect.models import InspectedFile, Inspection, Location
from descargo.modules.pre.inspect.odt import inspect_odt
from descargo.modules.pre.inspect.pdf import inspect_pdf

TEXT_SUFFIXES: Final = frozenset({".txt", ".text", ".md", ".markdown"})
DOCX_SUFFIXES: Final = frozenset({".docx", ".docm"})
SUFFIXES: Final = (*sorted(TEXT_SUFFIXES), *sorted(DOCX_SUFFIXES), ".odt", ".pdf")


def _text(data: bytes) -> FormatResult:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentError(f"not UTF-8 text ({exc.reason} at byte {exc.start})") from exc
    lines = text.split("\n")
    return FormatResult(
        segments=[
            Segment(Location(line=number), line.removesuffix("\r"))
            for number, line in enumerate(lines, start=1)
        ]
    )


def _zip(data: bytes, reader: Callable[[zipfile.ZipFile], FormatResult]) -> FormatResult:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return reader(archive)
    except zipfile.BadZipFile as exc:
        raise DocumentError(f"not a ZIP-based document: {exc}") from exc


def inspect_bytes(data: bytes, filename: str, *, today: date) -> Inspection:
    """Inspect ``data``, the content of ``filename``. Raises :class:`DocumentError`."""
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        fmt, result = "text", _text(data)
    elif suffix in DOCX_SUFFIXES:
        fmt, result = "docx", _zip(data, inspect_docx)
    elif suffix == ".odt":
        fmt, result = "odt", _zip(data, inspect_odt)
    elif suffix == ".pdf":
        fmt, result = "pdf", inspect_pdf(data)
    else:
        raise DocumentError(f"unsupported file type {suffix!r}; use {', '.join(SUFFIXES)}")
    findings = scan_characters(result.segments, text_file=fmt == "text") + result.findings
    return Inspection(
        generated_on=today,
        unidata_version=unicodedata.unidata_version,
        file=InspectedFile(
            filename=filename,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            format=fmt,
        ),
        findings=findings,
        metadata=result.metadata,
        notes=result.notes,
    )


def inspect_file(path: Path, *, today: date) -> Inspection:
    """Read ``path`` once, without modifying it, and inspect it."""
    return inspect_bytes(path.read_bytes(), path.name, today=today)
