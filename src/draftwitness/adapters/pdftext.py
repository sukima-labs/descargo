"""Text of a downloaded PDF report, shared by the adapters that read PDFs."""

import io
import unicodedata

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from draftwitness.adapters.base import AdapterError
from draftwitness.i18n import t


def open_pdf(data: bytes) -> PdfReader:
    """A reader for ``data``, or :class:`AdapterError` if it is not a readable PDF."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise AdapterError("the PDF is encrypted")
    except PdfReadError as exc:
        raise AdapterError(t("adapters.unreadable_pdf", error=exc)) from exc
    return reader


def pdf_lines(data: bytes) -> list[str]:
    """The report's text as :func:`normalized_lines`, all pages in order."""
    reader = open_pdf(data)
    try:
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise AdapterError(t("adapters.unreadable_pdf", error=exc)) from exc
    return normalized_lines("\n".join(pages))


def normalized_lines(text: str) -> list[str]:
    """Non-empty lines with ligatures expanded (NFKC: "Oﬀ" becomes "Off") and whitespace
    collapsed."""
    text = unicodedata.normalize("NFKC", text)
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]
