"""Read a Compilatio analysis report downloaded as PDF into the common report schema.

Two layouts are recognised (``labels.yaml``): Compilatio Magister until 2025
(:mod:`.magister`) and Compilatio Magister+ from 2026 (:mod:`.plus`), whose analysis
certificate is read too. Neither exposes the passages that match a source as text (they are
highlights), so the report carries sources but no matched passages, and the auditor uses its
approximate method (ADR 005), as with Turnitin. The passages attributed to AI are read from
their colour (Magister) or their underline (Magister+). Following ADR 004, the adapter never
keeps the depositor's name or the document ID, never invents a value it could not read, and
adds a warning instead.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Final

from pypdf import PdfReader

from descargo.adapters.base import AdapterError
from descargo.adapters.compilatio import magister, plus
from descargo.adapters.compilatio.common import Download, Words, labels
from descargo.adapters.pdftext import open_pdf, pdf_lines
from descargo.core.report_schema import Report

_Recognise = Callable[[list[str], Words], bool]
_Parse = Callable[[PdfReader, list[str], Words, str, Download], Report]
_LAYOUTS: Final[dict[str, tuple[_Recognise, _Parse]]] = {
    "magister": (magister.recognises, magister.parse),
    "magister_plus": (plus.recognises, plus.parse),
}


def detect_layout(lines: list[str]) -> tuple[str, str] | None:
    """The layout and language of the Compilatio report whose lines these are, or ``None``."""
    for layout, (recognises, _) in _LAYOUTS.items():
        for language, words in labels()[layout].items():
            if recognises(lines, words):
                return layout, language
    return None


def parse_pdf(
    data: bytes,
    filename: str,
    sha256: str,
    *,
    parsed_at: datetime,
    lines: list[str] | None = None,
) -> Report:
    """Turn a downloaded Compilatio PDF report into a :class:`Report`. ``lines`` are the
    report's :func:`~descargo.adapters.pdftext.pdf_lines`, if already extracted."""
    reader = open_pdf(data)
    lines = pdf_lines(data) if lines is None else lines
    found = detect_layout(lines)
    if found is None:
        raise AdapterError("not a Compilatio analysis report Descargo can read")
    layout, language = found
    parse = _LAYOUTS[layout][1]
    download = Download(data, filename, sha256, parsed_at)
    return parse(reader, lines, labels()[layout][language], language, download)
