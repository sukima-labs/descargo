"""Turnitin AI Writing Report, on synthetic PDFs that reproduce the line structure and the
cyan highlights pypdf reads from real downloaded reports (which are never committed)."""

import hashlib
import io
from collections.abc import Sequence
from datetime import timedelta, timezone

import pytest
from fpdf import FPDF
from pypdf import PdfReader

from descargo.adapters import AdapterError
from descargo.adapters.turnitin import detect_layout, parse_pdf
from descargo.adapters.turnitin.ai import parse_ai
from descargo.adapters.turnitin.pdf import _ai_footers, _ai_words, labels
from descargo.core.render.pdf import _font_path
from descargo.core.report_schema import Report, ReportKind, dump_report
from tests.test_turnitin_adapter import (
    AUTHOR,
    ENHANCED_COVER,
    NOW,
    SPANISH_COVER,
    SPANISH_ID,
    SPANISH_OVERVIEW,
    SPANISH_SOURCES,
)

ID = "trn:oid:::1:0000000002"
#: The highlight colour of real reports, in the 0-255 steps fpdf2 takes.
CYAN = (82, 198, 218)
#: Another highlight colour, as the Similarity Report uses for its sources.
PINK = (255, 105, 180)

# A line is plain text; ("ai", text) is drawn on a cyan box, ("path", text) on a cyan box
# drawn as a path of four points, as real reports do; ("pink", text) on a pink box.
Line = str | tuple[str, str]

COVER = [
    "Turnitin",
    "synthetic_essay",
    AUTHOR,
    *ENHANCED_COVER[3:17],
    "Page 1 of 3 - Cover Page",
    "Submission ID",
    ID,
]
COVER[COVER.index("trn:oid:::1:0000000001")] = ID
OVERVIEW = [
    "23% detected as AI",
    "The percentage indicates the combined amount of likely AI-generated text as",
    "well as likely AI-generated text that was also likely AI-paraphrased.",
    "Caution: Review required.",
    "Detection Groups",
    "1",
    "AI-generated only",
    "18%",
    "Likely AI-generated text from a large-language model.",
    "2",
    "AI-generated text that was AI-paraphrased",
    "5%",
    "Likely AI-generated text that was likely revised using an AI-paraphrase tool",
    "Page 2 of 3 - AI Writing Overview",
    f"Submission ID {ID}",
]
PAPER: list[Line] = [
    "SYNTHETIC essay on river basins",
    "A paragraph the student wrote, which is not highlighted.",
    ("ai", "This sentence is highlighted as AI,"),
    ("ai", "and so is its second line."),
    "Another plain paragraph.",
    ("path", "A passage highlighted with a path."),
    "Page 3 of 3 - AI Writing Submission",
    f"Submission ID {ID}",
]


def _pdf(*pages: Sequence[Line]) -> bytes:
    pdf = FPDF()
    pdf.add_font("Liberation", fname=_font_path("LiberationSerif-Regular.ttf"))
    pdf.set_font("Liberation", size=9)
    colours = {"ai": CYAN, "path": CYAN, "pink": PINK}
    for lines in pages:
        pdf.add_page()
        for line in lines:
            style, text = ("plain", line) if isinstance(line, str) else line
            if style == "path":
                x, y, width = pdf.get_x(), pdf.get_y(), pdf.get_string_width(text)
                pdf.set_fill_color(*colours[style])
                height = pdf.font_size  # the height of a cell, as the boxes cell(fill=True) draws
                corners = ((x, y), (x + width, y), (x + width, y + height), (x, y + height))
                pdf.polygon(corners, style="F")
                pdf.cell(text=text)
            elif style in colours:
                pdf.set_fill_color(*colours[style])
                pdf.cell(text=text, fill=True)
            else:
                pdf.cell(text=text)
            pdf.ln()
    return bytes(pdf.output())


def _parse(data: bytes) -> Report:
    return parse_pdf(data, "ai.pdf", hashlib.sha256(data).hexdigest(), parsed_at=NOW)


def test_ai_writing_report() -> None:
    report = _parse(_pdf(COVER, OVERVIEW, PAPER))
    assert report.tool.report_kind is ReportKind.AI_WRITING
    assert report.tool.product == "AI Writing Report"
    assert report.similarity is None
    ai = report.ai_writing
    assert ai is not None
    assert (ai.overall_percent, ai.label) == (23, None)
    assert [(s.page, s.text) for s in ai.segments] == [
        (3, "This sentence is highlighted as AI, and so is its second line."),
        (3, "A passage highlighted with a path."),
    ]
    assert report.submission.submission_id == ID
    assert report.submission.submitted_at is not None
    assert report.submission.submitted_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert report.submission.word_count == 3595
    extensions = report.extensions["turnitin"]
    assert extensions["layout"] == "ai_writing"
    assert extensions["ai_writing"] == {
        "language": "en",
        "below_threshold": False,
        "percent_is_upper_bound": False,
        "groups": {"ai_generated": 18, "ai_paraphrased": 5},
        "report_pages": 3,
    }
    warnings = " ".join(report.warnings)
    assert "highlights that text in purple" in warnings
    assert "cover page was not found" not in warnings
    assert "extract" not in warnings
    assert "approximate method" not in warnings
    assert AUTHOR not in dump_report(report)


def test_detect_layout_ai_writing() -> None:
    lines = [*OVERVIEW[:-2], "Page 2 of 3 - AI Writing Overview"]
    assert detect_layout(lines) == ("ai_writing", "en")
    assert detect_layout(lines[:-1]) is None


def test_ai_report_without_cover_or_paper() -> None:
    overview = [line.replace("of 3", "of 12") for line in OVERVIEW]
    report = _parse(_pdf(overview))
    assert report.submission.submission_id == ID
    warnings = " ".join(report.warnings)
    assert "The cover page was not found." in warnings
    assert "this PDF has none of the report's pages with the paper" in warnings
    assert "report has 12 pages but this PDF has 1" in warnings


def test_ai_report_with_unhighlighted_paper() -> None:
    paper = [line for line in PAPER if isinstance(line, str)]
    report = _parse(_pdf(COVER, OVERVIEW, paper))
    assert report.ai_writing is not None
    assert report.ai_writing.segments == []
    assert "no highlighted text was found" in " ".join(report.warnings)


def test_zero_percent_needs_no_passages() -> None:
    overview = [
        "0% detected as AI" if line.endswith("detected as AI") else line for line in OVERVIEW
    ]
    overview = ["0%" if line in {"18%", "5%"} else line for line in overview]
    paper = [line for line in PAPER if isinstance(line, str)]
    report = _parse(_pdf(COVER, overview, paper))
    assert report.ai_writing is not None
    assert report.ai_writing.overall_percent == 0
    assert not any("could not be read" in w or "purple" in w for w in report.warnings)


SPANISH_AI_ID = "trn:oid:::0000:00000002"
SPANISH_AI_COVER = [
    "Turnitin",
    *SPANISH_COVER[:-1],
    f"Página 1 de 3 - Portada Identificador de la entrega {SPANISH_AI_ID}",
]
SPANISH_AI_OVERVIEW = [
    "*% detectado como IA",
    "La detección de IA incluye la posibilidad de que haya falsos positivos.",
    "Precaución: Se necesita revisión.",
    "Página 2 de 3 - Descripción general de la escritura con IA",
    "Identificador de la entrega",
    SPANISH_AI_ID,
]
SPANISH_PAPER: list[Line] = [
    "1",
    ("pink", "Texto del trabajo que coincide con una fuente."),
    "Página 4 de 4 - Integrity Submission",
]


def test_similarity_and_ai_reports_in_one_pdf_in_spanish() -> None:
    ai_paper: list[Line] = [
        ("ai", "Un pasaje resaltado en cian."),
        "Página 3 de 3 - Entrega de escritura con IA",
    ]
    report = _parse(
        _pdf(
            SPANISH_COVER,
            SPANISH_OVERVIEW,
            SPANISH_SOURCES,
            SPANISH_PAPER,
            SPANISH_AI_COVER,
            SPANISH_AI_OVERVIEW,
            ai_paper,
        )
    )
    assert report.tool.report_kind is ReportKind.COMBINED
    assert report.tool.product == "Similarity Report + AI Writing Report"
    assert report.similarity is not None
    assert report.similarity.overall_percent == 19
    assert report.submission.submission_id == SPANISH_ID
    ai = report.ai_writing
    assert ai is not None
    assert (ai.overall_percent, ai.label) == (None, "*% detectado como IA")
    assert [s.page for s in ai.segments] == [7]
    extensions = report.extensions["turnitin"]
    assert extensions["language"] == "es"
    ai_extensions = extensions["ai_writing"]
    assert isinstance(ai_extensions, dict)
    assert ai_extensions["below_threshold"] is True
    assert ai_extensions["report_pages"] == 3
    warnings = " ".join(report.warnings)
    assert "under the 20 % threshold" in warnings
    assert "approximate method" in warnings
    assert "extract" not in warnings


def test_similarity_report_highlights_are_not_read_as_ai() -> None:
    paper: list[Line] = [("ai", "Cyan on a Similarity Report page."), SPANISH_PAPER[-1]]
    report = _parse(
        _pdf(
            SPANISH_COVER,
            SPANISH_OVERVIEW,
            SPANISH_SOURCES,
            paper,
            SPANISH_AI_COVER,
            SPANISH_AI_OVERVIEW,
        )
    )
    assert report.ai_writing is not None
    assert report.ai_writing.segments == []


def test_similarity_report_alone_has_no_ai_section() -> None:
    report = _parse(_pdf(SPANISH_COVER, SPANISH_OVERVIEW, SPANISH_SOURCES, SPANISH_PAPER))
    assert report.tool.report_kind is ReportKind.SIMILARITY
    assert report.ai_writing is None
    assert "ai_writing" not in report.extensions["turnitin"]


def test_score_is_required() -> None:
    data = _pdf(["No score here."])
    colour = (0.32, 0.78, 0.86)
    reader = PdfReader(io.BytesIO(data))
    with pytest.raises(AdapterError, match="AI writing percentage could not be read"):
        parse_ai(reader, ["No score here."], _ai_words("en"), _ai_footers("en"), colour)


def test_ai_labels_record_their_verification() -> None:
    entry = labels()["ai_writing"]
    assert entry["verification"] == "verified"
    assert entry["source"].strip()
    assert {"en", "es"} <= set(entry)
    assert len(entry["ai_generated_colour"]) == 3


def test_offset_of_spanish_cover() -> None:
    report = _parse(_pdf(SPANISH_AI_COVER, SPANISH_AI_OVERVIEW))
    assert report.submission.submission_id == SPANISH_ID
    assert report.submission.submitted_at is not None
    assert report.submission.submitted_at.tzinfo == timezone(timedelta(hours=-5))
