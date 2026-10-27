"""Read-only views of a student's document (plain text, DOCX, ODT, PDF)."""

from draftwitness.core.documents.text import (
    DocumentError,
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
