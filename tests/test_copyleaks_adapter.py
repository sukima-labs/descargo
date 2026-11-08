"""Copyleaks PDF adapter, on synthetic PDFs that reproduce the lines and the AI highlights
pypdf reads from real Copyleaks reports (read locally, never committed). Every name, title,
URL and id here is invented."""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fpdf import FPDF

from descargo.adapters import AdapterError, import_report
from descargo.adapters.copyleaks import detect_layout, parse_pdf
from descargo.adapters.pdftext import pdf_lines
from descargo.core.render.pdf import _font_path
from descargo.core.report_schema import Report, ReportKind, SourceKind, dump_report

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
#: The darkest step of Copyleaks' AI scale, in the 0-255 steps fpdf2 takes.
AI = (255, 102, 102)
#: A lighter red, as Copyleaks uses for minor changes on the plagiarism pages.
LIGHT = (255, 153, 153)
SUBMITTER = "NOMBRE INVENTADO"
SCAN_ID = "synthetic-scan-0001"

Line = str | tuple[tuple[int, int, int], str]


def _spaced(text: str) -> str:
    """A heading letter-spaced as Copyleaks prints it."""
    return " ".join(text.replace(" ", ""))


def _summary(ai: Sequence[str], overall: str = "74.5% 40%") -> list[str]:
    return [
        _spaced("Plagiarism and AI Content Detector Report"),
        "SYNTHETIC essay on rivers",
        "Scan details",
        "Submitted by:",
        SUBMITTER,
        "Scan time:",
        "March 3rd, 2026 at 14:05 UTC",
        "Total Pages:",
        "2",
        "Total Words:",
        "1,200",
        "Plagiarism Detection",
        "Types of plagiarism Words",
        "Identical 22.9% 275",
        "Minor Changes 10.4% 125",
        "Paraphrased 41.1% 493",
        "Omitted Words 0% 0",
        "AI Content Detection",
        *ai,
        _spaced("Disclamer"),
        "Alerts: (1)",
        "Cross Language: Same Document Language",
        "Submitted language and cross-language text are the same language.",
        "2/5 Severity",
        "Plagiarism Results: (5)",
        "A synthetic page about rivers",
        "https://www.example.org/rivers",
        "Example Org Rivers are long and they c...",
        "Paraphrased 45.3%",
        "Another page with a long title that is cu...",
        "https://www.example.net/another-page-with-a-long-...",
        "Skip to content ...",
        "Identical 2.6%",
        "Paraphrased 24%",
        _spaced("Certified by About this report"),
        "help.copyleaks.com",
        _spaced("copyleaks.com"),
        overall,
        "Copyleaks Internal Database",
        "No introduction available.",
        "99.4%",
        "A third page",
        "https://www.example.com/third",
        "...",
        "Identical 5%",
        "Identical 0.3%",
        _spaced("Results"),
    ]


AI_SHARE = ["Text coverage Words", "AI text 40% 480", "Human text 60% 720"]
CONTENT = [
    "Identical Minor Changes Paraphrased Omitted Words " + _spaced("Learn more"),
    "Plagiarism report content",
    "Rivers carry water from the hills to the sea.",
    "Scan id:",
    SCAN_ID,
]


def _ai_page(*lines: Line) -> list[Line]:
    return ["20% 40% 60% 80% 99% Omitted Content", "Scanned AI content", *lines]


def _pdf(*pages: Sequence[Line]) -> bytes:
    pdf = FPDF()
    pdf.add_font("Liberation", fname=_font_path("LiberationSerif-Regular.ttf"))
    pdf.set_font("Liberation", size=9)
    for lines in pages:
        pdf.add_page()
        for line in lines:
            if isinstance(line, str):
                pdf.cell(text=line)
            else:
                colour, text = line
                pdf.set_fill_color(*colour)
                pdf.cell(text=text, fill=True)
            pdf.ln()
    return bytes(pdf.output())


def _parse(data: bytes) -> Report:
    return parse_pdf(data, "copyleaks.pdf", hashlib.sha256(data).hexdigest(), parsed_at=NOW)


def _report_2023(ai_page: Sequence[Line] | None = None, ai: Sequence[str] = AI_SHARE) -> Report:
    pages: list[Sequence[Line]] = [_summary(ai), CONTENT]
    if ai_page is not None:
        pages.append(ai_page)
    return _parse(_pdf(*pages))


def test_2023_report_with_ai() -> None:
    # 480 of 1,200 words are AI: the highlighted passages must hold 480 words to avoid the
    # shades warning, so the test checks that warning instead (see the next test).
    report = _report_2023(
        _ai_page(
            "A sentence the student wrote.",
            (AI, "This sentence is on the AI colour,"),
            (AI, "and so is its second line."),
            (LIGHT, "A lighter shade is not read."),
            (AI, "A second passage."),
        )
    )
    assert report.tool.name == "copyleaks"
    assert report.tool.report_kind is ReportKind.COMBINED
    assert report.provenance.adapter == "copyleaks-pdf"
    assert report.submission.title == "SYNTHETIC essay on rivers"
    assert (report.submission.word_count, report.submission.page_count) == (1200, 2)
    similarity = report.similarity
    assert similarity is not None
    assert similarity.overall_percent == 74.5
    sources = [(s.rank, s.label, s.url, s.kind, s.percent) for s in similarity.sources]
    assert sources == [
        (
            1,
            "A synthetic page about rivers",
            "https://www.example.org/rivers",
            SourceKind.INTERNET,
            45.3,
        ),
        (
            2,
            "Another page with a long title that is cu...",
            "https://www.example.net/another-page-with-a-long-...",
            SourceKind.INTERNET,
            26.6,
        ),
        (3, "Copyleaks Internal Database", None, SourceKind.OTHER, 99.4),
        (4, "A third page", "https://www.example.com/third", SourceKind.INTERNET, 5.0),
    ]
    ai = report.ai_writing
    assert ai is not None
    assert ai.overall_percent == 40
    assert [(s.page, s.text) for s in ai.segments] == [
        (3, "This sentence is on the AI colour, and so is its second line."),
        (3, "A second passage."),
    ]
    extensions: dict[str, Any] = report.extensions["copyleaks"]
    assert extensions["layout"] == "report_2023"
    assert extensions["scanned_at"] == "2026-03-03T14:05:00+00:00"
    assert extensions["match_types"]["identical"] == {"percent": 22.9, "words": 275}
    assert extensions["alerts"] == [
        {"title": "Cross Language: Same Document Language", "severity": 2, "of": 5}
    ]
    assert extensions["source_shares_by_type"]["s2"] == {"identical": 2.6, "paraphrased": 24}
    assert (extensions["ai_words"], extensions["human_words"]) == (480, 720)
    warnings = " ".join(report.warnings)
    # A typed share repeated in one block starts a new block without a name.
    assert "has no name" in warnings
    assert "announces 5 results but 4 sources were read" in warnings
    assert "shortens long source names" in warnings
    assert "darkest shade" in warnings
    assert "do not name their source" in warnings


def test_ai_words_that_add_up_raise_no_shades_warning() -> None:
    passage = " ".join(["word"] * 12)
    report = _report_2023(
        _ai_page((AI, passage)),
        ai=["Text coverage Words", "AI text 100% 12", "Human text 0% 0"],
    )
    assert report.ai_writing is not None
    assert len(report.ai_writing.segments) == 1
    assert not any("darkest shade" in w for w in report.warnings)


def test_ai_percent_without_highlights() -> None:
    report = _report_2023(_ai_page("Nothing is highlighted here."))
    assert report.ai_writing is not None
    assert report.ai_writing.segments == []
    assert any("no highlighted text was found" in w for w in report.warnings)


def test_no_ai_result() -> None:
    lines = list(_summary(["Text coverage", "AI text", "Human text"], "100% N/A"))
    report = _parse(_pdf(lines, CONTENT))
    assert report.ai_writing is None
    assert report.tool.report_kind is ReportKind.SIMILARITY
    assert report.extensions["copyleaks"]["ai_result"] == "not_available"
    assert any("“N/A”" in w for w in report.warnings)
    assert report.similarity is not None
    assert report.similarity.overall_percent == 100


def test_ai_at_zero_reads_no_passages() -> None:
    report = _report_2023(ai=["Text coverage Words", "AI text 0% 0", "Human text 100% 1200"])
    assert report.ai_writing is not None
    assert report.ai_writing.overall_percent == 0
    assert report.ai_writing.segments == []
    assert not any("highlighted" in w for w in report.warnings)


def test_submitter_and_scan_id_are_never_kept() -> None:
    report = _report_2023(_ai_page((AI, "A passage.")))
    dumped = dump_report(report)
    assert SUBMITTER not in dumped
    assert SCAN_ID not in dumped


def test_overall_from_the_types_when_missing() -> None:
    lines = [line for line in _summary(AI_SHARE) if line != "74.5% 40%"]
    report = _parse(_pdf(lines, CONTENT))
    assert report.similarity is not None
    assert report.similarity.overall_percent == 74.4
    assert any("is the sum of" in w for w in report.warnings)


def test_no_overall_and_no_types_is_an_error() -> None:
    lines = [
        line
        for line in _summary(AI_SHARE)
        if line != "74.5% 40%" and not line.startswith(("Identical ", "Minor ", "Paraphrased "))
    ]
    with pytest.raises(AdapterError, match="overall similarity"):
        _parse(_pdf(lines, CONTENT))


def test_unreadable_scan_time() -> None:
    lines = [line.replace("March 3rd", "Marchy 3rd") for line in _summary(AI_SHARE)]
    report = _parse(_pdf(lines, CONTENT))
    assert report.extensions["copyleaks"]["scanned_at"] is None
    assert any("scan date" in w for w in report.warnings)


def test_plagiarism_report_heading_and_no_sources() -> None:
    lines = _summary(AI_SHARE)
    lines[0] = _spaced("Plagiarism report")
    lines = lines[: lines.index("Plagiarism Results: (5)")]
    report = _parse(_pdf(lines, CONTENT))
    assert report.similarity is not None
    assert report.similarity.sources == []
    assert any("No source list" in w for w in report.warnings)


SAMPLE_2022 = [
    "Synthetic-report.pdf",
    "Scanned on: 8:52 October 30, 2025 UTC",
    "Identical Words 76",
    "Words with Minor Changes 50",
    "Paraphrased Words 89",
    "Omitted Words 105",
    "Overall Similarity Score",
    "43.7%",
    "Results Found",
    "3",
    "Total Words in Text",
    "597",
    "Website | Education | Businesses",
    "Results",
    "Sources that matched your submitted document.",
    "A synthetic page",
    "https://www.example.org/a",
    "Another synthetic page with a long na...",
    "https://www.example.net/b-with-a-very-long-address...",
    "b-with-a-very-long-address-continued...",
    "Synthetic-report.pdf",
    "Scanned on: 8:52 October 30, 2025 UTC",
    "43%",
    "15%",
    "Website | Education | Businesses",
    ".",
    "A third page",
    "https://www.example.com/c",
    "Synthetic-report.pdf",
    "Scanned on: 8:52 October 30, 2025 UTC",
    "7%",
    "Scanned Text",
    "Your text is highlighted according to the matched content in the",
]


def test_2022_report() -> None:
    report = _parse(_pdf(SAMPLE_2022))
    assert report.tool.report_kind is ReportKind.SIMILARITY
    assert report.ai_writing is None
    assert report.submission.title == "Synthetic-report"
    assert report.submission.word_count == 597
    similarity = report.similarity
    assert similarity is not None
    assert similarity.overall_percent == 43.7
    assert [(s.label, s.url, s.percent) for s in similarity.sources] == [
        ("A synthetic page", "https://www.example.org/a", 43),
        (
            "Another synthetic page with a long na...",
            "https://www.example.net/b-with-a-very-long-address...",
            15,
        ),
        ("A third page", "https://www.example.com/c", 7),
    ]
    extensions: dict[str, Any] = report.extensions["copyleaks"]
    assert extensions["layout"] == "report_2022"
    assert extensions["scanned_at"] == "2025-10-30T08:52:00+00:00"
    assert extensions["match_types"]["omitted"] == {"words": 105}
    assert not any("misaligned" in w or "announces" in w for w in report.warnings)


def test_2022_report_with_misaligned_percentages() -> None:
    lines = [line for line in SAMPLE_2022 if line != "7%"]
    lines[lines.index("3")] = "4"
    report = _parse(_pdf(lines))
    assert report.similarity is not None
    assert report.similarity.sources[2].percent is None
    warnings = " ".join(report.warnings)
    assert "2 source percentages but 3 source names" in warnings
    assert "announces 4 results but 3 sources were read" in warnings


def test_detect_layout_and_import(tmp_path: Path) -> None:
    data = _pdf(_summary(AI_SHARE), CONTENT)
    assert detect_layout(pdf_lines(data)) == ("report_2023", "en")
    assert detect_layout(pdf_lines(_pdf(SAMPLE_2022))) == ("report_2022", "en")
    assert detect_layout(["Some other report", "Scan details"]) is None
    path = tmp_path / "copyleaks.pdf"
    path.write_bytes(data)
    report = import_report(path, parsed_at=NOW)
    assert report.tool.name == "copyleaks"
    assert report.provenance.report_file is not None
    assert report.provenance.report_file.sha256 == hashlib.sha256(data).hexdigest()


def test_not_copyleaks() -> None:
    with pytest.raises(AdapterError, match="not a Copyleaks report"):
        _parse(_pdf(["An unrelated document", "with two lines"]))
