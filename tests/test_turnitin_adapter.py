"""Turnitin PDF adapter, on synthetic PDFs that reproduce the line structure pypdf extracts
from real downloaded reports (which are never committed)."""

import copy
import hashlib
import io
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from draftwitness.adapters import AdapterError, import_report
from draftwitness.adapters.pdftext import normalized_lines
from draftwitness.adapters.turnitin import detect_layout, parse_pdf
from draftwitness.adapters.turnitin import pdf as turnitin_pdf
from draftwitness.adapters.turnitin.pdf import labels, parse_classic_date, parse_enhanced_date
from draftwitness.core.render.pdf import _font_path
from draftwitness.core.report_schema import Report, SourceKind, dump_report

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
AUTHOR = "Synthetic Student Name"

CLASSIC_COVER = [
    "SYNTHETIC essay on river basins",
    f"by {AUTHOR}",
    "Submission date: 22-Sep-2026 04:02PM (UTC+0800)",
    "Submission ID: 0000000001",
    "File name: synthetic_essay.docx (668.01K)",
    "Word count: 6,055",
    "Character count: 41070",
]
CLASSIC_REPORT = [
    "10%",
    "SIMILARITY INDEX",
    "11%",
    "INTERNET SOURCES",
    "7%",
    "PUBLICATIONS",
    "5%",
    "STUDENT PAPERS",
    "1 4%",
    "2 2%",
    "3 1%",
    "SYNTHETIC essay on river basins",
    "ORIGINALITY REPORT",
    "PRIMARY SOURCES",
    "www.example.org",
    "Internet Source",
    "Submitted to Synthetic University",
    "Student Paper",
    'A. Author, B. Author. "A long synthetic title that',
    'wraps over two lines", Journal of Examples, 2020',
    "Publication",
]
CLASSIC_PAGE_2 = [
    "4 <1%",
    "Exclude quotes Off",
    "Exclude bibliography On",
    "Exclude matches < 15 words",
    "docs.example.net",
    "Internet Source",
    "SYNTHETIC essay on river basins",
    "PAGE 1",
    "PAGE 2",
]

ENHANCED_COVER = [
    "Turnitin",
    "synthetic_essay",
    AUTHOR,
    "Document Details",
    "Submission ID",
    "trn:oid:::1:0000000001",
    "Submission Date",
    "Mar 19, 2026, 3:33 PM GMT+5:30",
    "Download Date",
    "Mar 19, 2026, 3:37 PM GMT+5:30",
    "File Name",
    "synthetic_essay.docx",
    "File Size",
    "24.9 KB",
    "14 Pages",
    "3,595 Words",
    "21,691 Characters",
    "Page 1 of 4 - Cover Page",
    "Submission ID",
    "trn:oid:::1:0000000001",
]
ENHANCED_OVERVIEW = [
    "24%",
    "Overall Similarity",
    "The combined total of all matches, including overlapping sources, for each database.",
    "Filtered from the Report",
    "Bibliography",
    "Small Matches (less than 8 words)",
    "Exclusions",
    "3 Excluded Matches",
    "1 Excluded Source",
    "Match Groups",
    "68",
    "Not Cited or Quoted 20%",
    "Matches with neither in-text citation nor quotation marks",
    "1",
    "Missing Quotations 1%",
    "Matches that are still very similar to source material",
    "0",
    "Missing Citation 0%",
    "Matches that have quotation marks, but no in-text citation",
    "4",
    "Cited and Quoted 3%",
    "Matches with in-text citation present, but no quotation marks",
    "Top Sources",
    "21%",
    "Internet sources",
    "18%",
    "Publications",
    "2%",
    "Submitted works (Student Papers)",
    "Integrity Flags",
    "1 Integrity Flags for Review",
    "Page 2 of 4 - Integrity Overview",
    "Submission ID",
    "trn:oid:::1:0000000001",
]
ENHANCED_SOURCES = [
    "Top Sources",
    "The sources with the highest number of matches within the submission. Overlapping "
    "sources will not be displayed.",
    "1",
    "Internet",
    "www.example.org",
    "4%",
    "2",
    "Publication",
    'A. Author, B. Author. "A long synthetic title that is cut...',
    "<1%",
    "Page 3 of 4 - Integrity Overview",
    "Submission ID",
    "trn:oid:::1:0000000001",
    "3",
    "Submitted works",
    "Synthetic University on 2026-01-01",
    "<1%",
    "Page 3 of 4 - Integrity Overview",
    "Submission ID",
    "trn:oid:::1:0000000001",
]
ENHANCED_PAPER = [
    "SYNTHETIC essay on river basins",
    "1",
    "Page 4 of 4 - Integrity Submission",
    "Submission ID",
    "trn:oid:::1:0000000001",
]


def _pdf(*pages: list[str], encrypt: str | None = None) -> bytes:
    pdf = FPDF()
    pdf.set_creation_date(NOW)
    pdf.add_font("Liberation", fname=_font_path("LiberationSerif-Regular.ttf"))
    pdf.set_font("Liberation", size=9)
    for lines in pages:
        pdf.add_page()
        for line in lines:
            pdf.cell(text=line)
            pdf.ln()
    data = bytes(pdf.output())
    if encrypt is None:
        return data
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.encrypt(encrypt, algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _parse(data: bytes, filename: str = "report.pdf") -> Report:
    return parse_pdf(data, filename, hashlib.sha256(data).hexdigest(), parsed_at=NOW)


def _classic(*extra: list[str]) -> bytes:
    return _pdf(CLASSIC_COVER, ["Body of the essay."], CLASSIC_REPORT, CLASSIC_PAGE_2, *extra)


def _enhanced(
    *, cover: list[str] = ENHANCED_COVER, overview: list[str] = ENHANCED_OVERVIEW
) -> bytes:
    return _pdf(cover, overview, ENHANCED_SOURCES, ENHANCED_PAPER)


# --- Feedback Studio ----------------------------------------------------------------------


def test_feedback_studio_report() -> None:
    data = _classic()
    report = _parse(data, "downloaded.pdf")
    assert report.tool.name == "turnitin"
    assert report.tool.product == "Feedback Studio"
    assert report.provenance.adapter == "turnitin-pdf"
    assert report.provenance.report_file is not None
    assert report.provenance.report_file.sha256 == hashlib.sha256(data).hexdigest()
    assert report.provenance.report_file.size_bytes == len(data)
    submission = report.submission
    assert submission.title == "SYNTHETIC essay on river basins"
    assert submission.submission_id == "0000000001"
    assert submission.submitted_at == datetime(
        2026, 9, 22, 16, 2, tzinfo=timezone(timedelta(hours=8))
    )
    assert submission.word_count == 6055
    assert submission.character_count == 41070
    similarity = report.similarity
    assert similarity is not None
    assert similarity.overall_percent == 10
    assert similarity.filters.quotes_excluded is False
    assert similarity.filters.bibliography_excluded is True
    assert similarity.filters.small_matches_excluded is True
    assert similarity.filters.small_matches_min_words == 15
    assert [(s.rank, s.kind, s.percent, s.percent_is_upper_bound) for s in similarity.sources] == [
        (1, SourceKind.INTERNET, 4, False),
        (2, SourceKind.STUDENT_PAPER, 2, False),
        (3, SourceKind.PUBLICATION, 1, False),
        (4, SourceKind.INTERNET, 1, True),
    ]
    assert similarity.sources[2].label == (
        'A. Author, B. Author. "A long synthetic title that wraps over two lines", '
        "Journal of Examples, 2020"
    )
    assert similarity.matches == []
    assert report.extensions["turnitin"] == {
        "layout": "feedback_studio",
        "language": "en",
        "databases": {"internet": 11, "publications": 7, "student_papers": 5},
    }
    assert len(report.warnings) == 1
    assert "approximate method" in report.warnings[0]


def test_author_and_file_name_are_not_kept() -> None:
    for data in (_classic(), _enhanced()):
        text = dump_report(_parse(data))
        assert AUTHOR not in text
        assert "synthetic_essay.docx (668.01K)" not in text
        assert "24.9 KB" not in text


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Exclude matches Off", {"small_matches_excluded": False}),
        ("Exclude matches < 1%", {"small_matches_excluded": True, "small_matches_min_percent": 1}),
        (
            "Exclude matches < 15 words",
            {"small_matches_excluded": True, "small_matches_min_words": 15},
        ),
        ("Exclude matches sometimes", {}),
    ],
)
def test_feedback_studio_small_matches(line: str, expected: dict[str, object]) -> None:
    page = [line if item.startswith("Exclude matches") else item for item in CLASSIC_PAGE_2]
    report = _parse(_pdf(CLASSIC_COVER, CLASSIC_REPORT, page))
    assert report.similarity is not None
    filters = report.similarity.filters.model_dump(exclude_none=True)
    filters.pop("quotes_excluded")
    filters.pop("bibliography_excluded")
    assert filters == expected


def test_feedback_studio_unknown_switch_and_missing_cover() -> None:
    page = ["Exclude quotes Maybe" if i.startswith("Exclude quotes") else i for i in CLASSIC_PAGE_2]
    report = _parse(_pdf(["Untitled"], CLASSIC_REPORT, page))
    assert report.similarity is not None
    assert report.similarity.filters.quotes_excluded is None
    assert report.submission.title is None
    assert report.submission.word_count is None


def test_feedback_studio_misaligned_and_leftover_text() -> None:
    page = [*CLASSIC_PAGE_2[:6], "Some stray footer"]
    report_page = [*CLASSIC_REPORT[:8], "5 1%", *CLASSIC_REPORT[8:]]
    report = _parse(_pdf(CLASSIC_COVER, report_page, ["Internet Source", *page]))
    joined = " ".join(report.warnings)
    assert "5 source percentages but 4 source names" in joined
    assert "has no name" in joined
    assert "not recognised as a source" in joined


def test_feedback_studio_bad_date() -> None:
    cover = [
        "Submission date: someday" if i.startswith("Submission date") else i for i in CLASSIC_COVER
    ]
    report = _parse(_pdf(cover, CLASSIC_REPORT, CLASSIC_PAGE_2))
    assert report.submission.submitted_at is None
    assert any("submission date" in w for w in report.warnings)


# --- Enhanced Similarity Report -----------------------------------------------------------


def test_enhanced_report() -> None:
    report = _parse(_enhanced())
    assert report.tool.product == "Similarity Report"
    submission = report.submission
    assert submission.title == "synthetic_essay"
    assert submission.submission_id == "trn:oid:::1:0000000001"
    assert submission.submitted_at == datetime(
        2026, 3, 19, 15, 33, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    assert (submission.page_count, submission.word_count, submission.character_count) == (
        14,
        3595,
        21691,
    )
    similarity = report.similarity
    assert similarity is not None
    assert similarity.overall_percent == 24
    assert similarity.filters.model_dump(exclude_none=True) == {
        "quotes_excluded": False,
        "bibliography_excluded": True,
        "small_matches_excluded": True,
        "small_matches_min_words": 8,
    }
    assert [(s.rank, s.kind, s.percent, s.percent_is_upper_bound) for s in similarity.sources] == [
        (1, SourceKind.INTERNET, 4, False),
        (2, SourceKind.PUBLICATION, 1, True),
        (3, SourceKind.STUDENT_PAPER, 1, True),
    ]
    assert report.extensions["turnitin"] == {
        "layout": "enhanced",
        "language": "en",
        "cited_text_excluded": False,
        "excluded_matches": 3,
        "match_groups": {
            "not_cited_or_quoted": {"matches": 68, "percent": 20},
            "missing_quotations": {"matches": 1, "percent": 1},
            "missing_citation": {"matches": 0, "percent": 0},
            "cited_and_quoted": {"matches": 4, "percent": 3},
        },
        "databases": {"internet": 21, "publications": 18, "submitted_works": 2},
        "integrity_flags": 1,
        "integrity_flag_notes": [],
        "sections": ["Cover Page", "Integrity Overview", "Integrity Submission"],
        "report_pages": 4,
    }
    joined = " ".join(report.warnings)
    assert "has not yet been checked" in joined  # "Small Matches" label
    assert "shortens long source names" in joined


def test_enhanced_title_is_dropped_when_it_cannot_be_told_from_the_author() -> None:
    cover = [i.replace("synthetic_essay.docx", "other.docx") for i in ENHANCED_COVER]
    report = _parse(_enhanced(cover=cover))
    assert report.submission.title is None
    assert any("could not be told apart" in w for w in report.warnings)


def test_enhanced_without_filters_or_cover() -> None:
    overview = [
        line
        for line in ENHANCED_OVERVIEW
        if line
        not in {"Filtered from the Report", "Bibliography", "Small Matches (less than 8 words)"}
    ]
    report = _parse(_pdf(["Turnitin"], overview, ENHANCED_SOURCES, ENHANCED_PAPER))
    assert report.similarity is not None
    assert report.similarity.filters.bibliography_excluded is None
    assert any("cover page was not found" in w for w in report.warnings)


def test_enhanced_unrecognised_filter_and_rank_gap() -> None:
    overview = ["Quoted Text" if line == "Bibliography" else line for line in ENHANCED_OVERVIEW]
    overview.insert(overview.index("Exclusions"), "Something New")
    sources = ["4" if line == "3" else line for line in ENHANCED_SOURCES]
    report = _parse(_pdf(ENHANCED_COVER, overview, sources, ENHANCED_PAPER))
    assert report.similarity is not None
    assert report.similarity.filters.quotes_excluded is True
    joined = " ".join(report.warnings)
    assert "Unrecognised filter on the report: “Something New”" in joined
    assert "not numbered 1, 2, 3" in joined


def test_enhanced_bad_date_and_zero_report() -> None:
    cover = ["someday" if i.startswith("Mar 19") else i for i in ENHANCED_COVER]
    overview = ["0%" if line == "24%" else line for line in ENHANCED_OVERVIEW]
    report = _parse(_pdf(cover, overview, ENHANCED_PAPER))
    assert report.submission.submitted_at is None
    assert report.similarity is not None
    assert report.similarity.sources == []
    assert any("No source list" in w for w in report.warnings)


def test_source_above_overall_is_flagged() -> None:
    overview = ["3%" if line == "24%" else line for line in ENHANCED_OVERVIEW]
    report = _parse(_pdf(ENHANCED_COVER, overview, ENHANCED_SOURCES, ENHANCED_PAPER))
    assert any("misread or edited" in w for w in report.warnings)


# --- Detection and errors -----------------------------------------------------------------


def test_normalized_lines() -> None:
    assert normalized_lines("Exclude quotes O\ufb00\n\n  a\u00a0 b \n") == [
        "Exclude quotes Off",
        "a b",
    ]


def test_detect_layout() -> None:
    assert detect_layout(["ORIGINALITY REPORT", "SIMILARITY INDEX", "PRIMARY SOURCES"]) == (
        "feedback_studio",
        "en",
    )
    assert detect_layout(["Overall Similarity", "Page 2 of 3 - Integrity Overview"]) == (
        "enhanced",
        "en",
    )
    assert detect_layout(["Overall Similarity"]) is None


def test_unknown_layout() -> None:
    with pytest.raises(AdapterError, match="not a Turnitin report"):
        _parse(_pdf(["An ordinary PDF."]))


def test_overall_percentage_missing() -> None:
    overview = ["n/a" if line == "24%" else line for line in ENHANCED_OVERVIEW]
    with pytest.raises(AdapterError, match="overall similarity"):
        _parse(_pdf(overview))


def test_encrypted_and_broken_pdfs() -> None:
    with pytest.raises(AdapterError, match="encrypted"):
        _parse(_pdf(ENHANCED_OVERVIEW, encrypt="synthetic"))
    with pytest.raises(AdapterError, match="cannot read PDF"):
        _parse(b"%PDF-1.4 garbage")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "22-Sep-2026 04:02PM (UTC+0800)",
            datetime(2026, 9, 22, 16, 2, tzinfo=timezone(timedelta(hours=8))),
        ),
        (
            "01-Jan-2026 12:15AM (UTC-0500)",
            datetime(2026, 1, 1, 0, 15, tzinfo=timezone(timedelta(hours=-5))),
        ),
        ("22-Foo-2026 04:02PM (UTC+0800)", None),
        ("soon", None),
    ],
)
def test_parse_classic_date(text: str, expected: datetime | None) -> None:
    assert parse_classic_date(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Jul 11, 2026, 8:04 AM GMT+7",
            datetime(2026, 7, 11, 8, 4, tzinfo=timezone(timedelta(hours=7))),
        ),
        ("Dec 1, 2026, 12:00 PM GMT", datetime(2026, 12, 1, 12, 0, tzinfo=UTC)),
        (
            "Oct 5, 2026, 9:30 PM GMT-5",
            datetime(2026, 10, 5, 21, 30, tzinfo=timezone(timedelta(hours=-5))),
        ),
        ("Foo 5, 2026, 9:30 PM GMT", None),
    ],
)
def test_parse_enhanced_date(text: str, expected: datetime | None) -> None:
    assert parse_enhanced_date(text) == expected


def test_labels_record_their_verification() -> None:
    for layout in ("feedback_studio", "enhanced"):
        entry = labels()[layout]
        assert entry["verification"] in {"verified", "needs_verification"}
        assert entry["source"].strip()
        assert "en" in entry


# --- import_report ------------------------------------------------------------------------


def test_import_report_dispatches_by_suffix(tmp_path: Path, fixtures_dir: Path) -> None:
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(_enhanced())
    assert import_report(pdf, parsed_at=NOW).tool.name == "turnitin"
    report = import_report(fixtures_dir / "reports" / "similarity_full.json", parsed_at=NOW)
    assert report.provenance.adapter == "manual"
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(AdapterError, match="not a valid DraftWitness report"):
        import_report(bad, parsed_at=NOW)
    html = tmp_path / "report.html"
    html.write_text("<p>report</p>", encoding="utf-8")
    with pytest.raises(AdapterError, match="unsupported report type"):
        import_report(html, parsed_at=NOW)


def test_a_new_language_needs_only_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    data = copy.deepcopy(labels())
    data["enhanced"]["xx"] = {**data["enhanced"]["en"], "overall": "Similitud general"}
    del data["enhanced"]["en"]
    monkeypatch.setattr(turnitin_pdf, "labels", lambda: data)
    overview = ["Similitud general" if i == "Overall Similarity" else i for i in ENHANCED_OVERVIEW]
    report = _parse(_pdf(ENHANCED_COVER, overview, ENHANCED_SOURCES, ENHANCED_PAPER))
    assert report.extensions["turnitin"]["language"] == "xx"
    assert report.similarity is not None
    assert report.similarity.overall_percent == 24


# --- Enhanced, in Spanish -----------------------------------------------------------------

SPANISH_ID = "trn:oid:::0000:00000001"
SPANISH_COVER = [
    "SYNTHETIC Informe de bachillerato de",
    "dos lineas.pdf",
    AUTHOR,
    "Detalles del documento",
    "Identificador de la entrega",
    SPANISH_ID,
    "Fecha de entrega",
    "29 ene 2026, 9:02 p.m. GMT-5",
    "Fecha de descarga",
    "29 ene 2026, 9:07 p.m. GMT-5",
    "Nombre de archivo",
    "SYNTHETIC Informe de bachillerato de dos lineas.pdf",
    "Tamaño de archivo",
    "486.3 KB",
    "28 Páginas",
    "6,588 Palabras",
    "37,494 Caracteres",
    f"Página 1 of 4 - Portada Identificador de la entrega {SPANISH_ID}",
]
SPANISH_OVERVIEW = [
    "19% Similitud general",
    "El total combinado de todas las coincidencias, incluidas las fuentes superpuestas.",
    "Filtrado desde el informe",
    "Bibliografía",
    "Exclusiones",
    "N.º de coincidencias excluidas",
    "Fuentes principales",
    "19% Fuentes de Internet",
    "3%",
    "Publicaciones",
    "0%",
    "Trabajos entregados (trabajos del estudiante)",
    "Marcas de integridad",
    "N.º de alerta de integridad para revisión",
    "Texto oculto",
    "4 caracteres sospechosos en N.º de páginas",
    "El texto es alterado para mezclarse con el fondo blanco del documento.",
    "Los algoritmos de nuestro sistema analizan un documento en profundidad.",
    "Página 2 de 4 - Descripción general de integridad",
    "Identificador de la entrega",
    SPANISH_ID,
]
SPANISH_SOURCES = [
    "Fuentes principales",
    "Las fuentes con el mayor número de coincidencias dentro de la entrega. Las fuentes "
    "superpuestas no se mostrarán.",
    "1",
    "Internet",
    "www.example.org",
    "6%",
    "2",
    "Publicación",
    'A. Autora. "Un título sintético largo…',
    "<1%",
    "3",
    "Trabajos del estudiante",
    "Synthetic University",
    "<1%",
    "Página 3 de 4 - Descripción general de integridad",
    f"Identificador de la entrega {SPANISH_ID}",
]
SPANISH_PAPER = ["1", "Texto del trabajo.", "Página 4 de 4 - Integrity Submission"]


def test_enhanced_report_in_spanish() -> None:
    report = _parse(_pdf(SPANISH_COVER, SPANISH_OVERVIEW, SPANISH_SOURCES, SPANISH_PAPER))
    extensions = report.extensions["turnitin"]
    assert extensions["language"] == "es"
    assert report.submission.title == "SYNTHETIC Informe de bachillerato de dos lineas.pdf"
    assert report.submission.submission_id == SPANISH_ID
    assert report.submission.submitted_at == datetime(
        2026, 1, 29, 21, 2, tzinfo=timezone(timedelta(hours=-5))
    )
    assert (report.submission.page_count, report.submission.word_count) == (28, 6588)
    assert report.similarity is not None
    assert report.similarity.overall_percent == 19
    assert report.similarity.filters.bibliography_excluded is True
    assert extensions["databases"] == {"internet": 19, "publications": 3, "submitted_works": 0}
    assert extensions["sections"] == [
        "Portada",
        "Descripción general de integridad",
        "Integrity Submission",
    ]
    assert extensions["integrity_flag_notes"] == [
        "Texto oculto",
        "4 caracteres sospechosos en N.o de páginas",
        "El texto es alterado para mezclarse con el fondo blanco del documento.",
    ]
    rows = [(s.rank, s.kind, s.percent, s.label) for s in report.similarity.sources]
    assert rows == [
        (1, SourceKind.INTERNET, 6, "www.example.org"),
        (2, SourceKind.PUBLICATION, 1, 'A. Autora. "Un título sintético largo...'),
        (3, SourceKind.UNKNOWN, 1, "Synthetic University"),
    ]
    warnings = " ".join(report.warnings)
    assert "integrity flags: Texto oculto" in warnings
    assert "a type the adapter does not know: “Trabajos del estudiante”" in warnings
    assert AUTHOR not in dump_report(report)


def test_enhanced_extract_and_unreadable_source_list() -> None:
    overview = [line.replace("de 4", "de 40") for line in SPANISH_OVERVIEW]
    sources = [*SPANISH_SOURCES[:2], "www.example.org 6%"]
    report = _parse(_pdf(overview, sources))
    warnings = " ".join(report.warnings)
    assert "The cover page was not found." in warnings
    assert "report has 40 pages but this PDF has 2" in warnings
    assert "saved again through another program" in warnings
    assert "No source list was read" not in warnings
    assert report.submission.submission_id == SPANISH_ID


def test_parse_enhanced_date_in_spanish() -> None:
    months = labels()["enhanced"]["es"]["months"]
    assert parse_enhanced_date("1 nov 2025, 3:18 a.m. GMT+5", months) == datetime(
        2025, 11, 1, 3, 18, tzinfo=timezone(timedelta(hours=5))
    )
    assert parse_enhanced_date("31 feb 2025, 3:18 a.m. GMT", months) is None
    assert parse_enhanced_date("1 xyz 2025, 3:18 a.m. GMT", months) is None
