"""Read-only views of a student's document (plain text, DOCX, ODT, PDF)."""

from descargo.core.documents.archive import DocumentError
from descargo.core.documents.text import (
    Paragraph,
    TextDocument,
    count_words,
    extract_text,
    text_document,
)

__all__ = [
    "DocumentError",
    "Paragraph",
    "TextDocument",
    "count_words",
    "extract_text",
    "text_document",
]
