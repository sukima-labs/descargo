"""Compilatio Magister+ (2026) PDF adapter, on synthetic PDFs that reproduce what pypdf
extracts from real Spanish Magister+ reports (read locally, never committed): the summary
lines, source tables drawn a column at a time, and AI passages underlined with a thin bar.
Every name, title and URL here is invented."""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime

from fpdf import FPDF

from draftwitness.adapters.compilatio import detect_layout, parse_pdf
from draftwitness.adapters.pdftext import pdf_lines
from draftwitness.core.render.pdf import _font_path
from draftwitness.core.report_schema import Report, SourceKind, dump_report

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
INK = (31, 41, 56)
GREY = (107, 115, 130)
BLACK = (0, 0, 0)
AI = (0, 191, 255)
ROW_COLOURS = [(255, 217, 41), (199, 217, 59), (143, 217, 77), (89, 217, 94), (59, 214, 125)]

SUMMARY = [
    "Informe de análisis",
    "Compilatio Magister+ | SYNTHETIC University",
    "SYNTHETIC Trabajo final",
    "ID : 0000000000000000000000000000000000000000",
    "34%",
    "Textos sospechosos",
    "Nombre del fichero : SYNTHETIC Trabajo",
    "final.txt",
    "Tamaño del archivo original : 12,5 kB",
    "Número de palabras : 1.234",
    "Número de caracteres : 8765",
    "Depositante : NOMBRE INVENTADO",
    "Fecha de depósito : 5 de octubre de 2026",
    "Tipo de carga : interface",
    "fecha de fin de análisis : 6 de octubre de 2026",
    "Resumen (sección 1/3)",
    "Incluido en el porcentaje de textos sospechosos :",
    "Similitudes",
    "Sintáctica 6% Semántica 7%",
    "Pasajes con similitudes a fuentes encontradas en diferentes colecciones.",
    "13%",
    "Detección de IA",
    "Textos estilísticamente próximos a un texto generado por una IA.",
    "12%",
    "Idiomas no reconocidos",
    "Pasajes en los que parte del vocabulario utilizado no forma parte del diccionario.",
    "2%",
    "No incluido en el porcentaje de textos sospechosos :",
    "Textos entre comillas",
    "Pasajes entre comillas, a menudo indicativos de una cita.",
    "<1%",
]

# (number, label in the row's colour, grey pieces as (x, offset from the number's
# baseline, text), percentage). A piece with no x runs on from the one before it.
Row = tuple[int, str, list[tuple[float | None, float, str]], str]
ROWS: list[Row] = [
    (
        1,
        "www.example.org",
        [(112, 6, "www.example.org"), (None, 6, "/a/very/long/path/that/is/cut"), (None, 6, "…")],
        "3%",
    ),
    (
        2,
        "Documento de otro usuario",
        [
            (240, -6, " #0a1b2c"),
            (282, -6, " Detección semántica"),
            (130, 4, "Viene de de otro grupo"),
        ],
        "2%",
    ),
    (3, "Synthetic page title of a", [(112, 6, "docs.example.net"), (None, 6, "/page")], "<1%"),
    (4, "Lock", [(112, 6, "pmc.example.gov"), (None, 6, "/articles/PMC1/")], "<1%"),
    (
        5,
        "SYNTHETIC thesis by someone",
        [(240, -6, " #d4e5f6"), (130, 4, "Viene de de mi biblioteca")],
        "<1%",
    ),
]


class _Page:
    """Draws text at positions, in points from the top left, like Chromium's PDFs do."""

    def __init__(self, pdf: FPDF) -> None:
        self.pdf = pdf
        pdf.add_page()

    def text(self, x: float, y: float, text: str, colour: tuple[int, int, int] = INK) -> None:
        self.pdf.set_text_color(*colour)
        self.pdf.text(x, y, text)

    def bar(self, x: float, y: float, width: float, colour: tuple[int, int, int] = AI) -> None:
        self.pdf.set_fill_color(*colour)
        self.pdf.rect(x, y, width, 1.4, style="F")


def _new() -> FPDF:
    pdf = FPDF(unit="pt", format=(596, 843))
    pdf.set_creation_date(NOW)
    pdf.add_font("Liberation", fname=_font_path("LiberationSerif-Regular.ttf"))
    pdf.set_font("Liberation", size=8)
    pdf.set_auto_page_break(False)
    return pdf


def _summary(pdf: FPDF, lines: Sequence[str]) -> None:
    page = _Page(pdf)
    for index, line in enumerate(lines):
        page.text(30, 30 + index * 11, line)


def _header(page: _Page, y: float, similarity: bool = True) -> None:
    page.text(34, y, "N°", GREY)
    page.text(110, y, " Descripciones", GREY)
    if similarity:
        page.text(407, y, " Similitudes", GREY)
        page.text(493, y, " Ubicaciones", GREY)


def _sources(pdf: FPDF) -> None:
    """Rows 1-3 are main sources, 4-5 incidental. As in the real PDFs, the percentages and
    the incidental heading come out before the rows they belong to."""
    page = _Page(pdf)
    page.text(45, 40, "Fuentes de similitudes")
    page.text(205, 40, " (sección 2/3)", GREY)
    page.text(22, 60, "Fuente principal detectada")
    _header(page, 80)
    tops = [110, 160, 210, 290, 340]
    for top, (_, _, _, percent) in zip(tops, ROWS, strict=True):
        if percent.startswith("<"):
            page.text(427, top, percent[:-1], BLACK)
        else:
            page.text(431, top, percent[:-1], BLACK)
        page.text(441, top, "%", BLACK)
    page.text(22, 250, "Fuente con similitudes fortuitas")
    for top, colour, (number, label, grey, _) in zip(tops, ROW_COLOURS, ROWS, strict=True):
        page.text(34, top, str(number), colour)
        page.text(110, top - 6, f" {label}", colour)
        end = 0.0
        for x, offset, piece in grey:
            start = end if x is None else x
            page.text(start, top + offset, piece, GREY)
            end = start + pdf.get_string_width(piece)
    page.text(22, 400, "Fuente mencionada (sin similitudes detectadas)")
    _header(page, 420, similarity=False)
    page.text(42, 440, "1", GREY)
    page.text(128, 440, " https://www.example.com/cited", GREY)


def _body(pdf: FPDF) -> None:
    """Section 3: the document, with two passages underlined in the AI colour, one of
    them over two lines, and source numbers in the margin."""
    page = _Page(pdf)
    plain = "Una frase normal y luego"
    marked = 124 + pdf.get_string_width(plain)
    page.bar(marked, 100.6, 120)
    page.bar(124, 117.6, 150)
    page.bar(124, 151.6, 110)
    page.text(45, 40, "Puntos de interés")
    page.text(172, 40, " (sección 3/3)", GREY)
    page.text(124, 80, "Introducción escrita por la persona autora.", BLACK)
    page.text(124, 97, plain, BLACK)
    page.text(marked, 97, " este pasaje sintético", BLACK)
    page.text(124, 114, "que sigue en la línea siguiente.", BLACK)
    page.text(124, 131, "Texto propio otra vez.", BLACK)
    page.text(124, 148, "Un segundo pasaje marcado.", BLACK)
    page.text(33, 148, "1", ROW_COLOURS[0])
    page.text(124, 165, "Cierre sin marcar.", BLACK)


def _report(summary: Sequence[str] = SUMMARY, *, body: bool = True) -> bytes:
    pdf = _new()
    _summary(pdf, summary)
    _sources(pdf)
    if body:
        _body(pdf)
    return bytes(pdf.output())


def _parse(data: bytes) -> Report:
    return parse_pdf(data, "informe.pdf", hashlib.sha256(data).hexdigest(), parsed_at=NOW)


def test_reads_the_summary() -> None:
    data = _report()
    assert detect_layout(pdf_lines(data)) == ("magister_plus", "es")
    report = _parse(data)
    assert report.tool.product == "Compilatio Magister+"
    assert report.provenance.adapter_version == "0.2"
    assert report.submission.title == "SYNTHETIC Trabajo final"
    assert (report.submission.word_count, report.submission.character_count) == (1234, 8765)
    assert report.similarity is not None
    assert report.similarity.overall_percent == 13
    assert report.ai_writing is not None
    assert report.ai_writing.overall_percent == 12
    extensions = report.extensions["compilatio"]
    assert extensions["layout"] == "magister_plus"
    assert extensions["document"] == "report"
    assert (extensions["deposited_on"], extensions["analysed_on"]) == ("2026-10-05", "2026-10-06")
    assert extensions["suspicious_percent"] == 34
    assert extensions["unrecognised_languages_percent"] == 2
    assert (extensions["quoted_percent"], extensions["quoted_percent_is_upper_bound"]) == (1, True)
    assert extensions["syntactic_similarity_percent"] == 6
    assert extensions["semantic_similarity_percent"] == 7
    assert extensions["included_in_suspicious"] == {
        "similarity": True,
        "ai": True,
        "unrecognised_languages": True,
        "quoted": False,
    }


def test_puts_source_rows_back_together() -> None:
    report = _parse(_report())
    assert report.similarity is not None
    rows = [
        (s.id, s.rank, s.kind, s.percent, s.percent_is_upper_bound, s.label, s.url)
        for s in report.similarity.sources
    ]
    assert rows == [
        ("m1", 1, SourceKind.INTERNET, 3, False, "www.example.org", None),
        ("m2", 2, SourceKind.STUDENT_PAPER, 2, False, "Documento de otro usuario", None),
        (
            "m3",
            3,
            SourceKind.INTERNET,
            1,
            True,
            "Synthetic page title of a",
            "docs.example.net/page",
        ),
        (
            "i4",
            4,
            SourceKind.INTERNET,
            1,
            True,
            "pmc.example.gov/articles/PMC1/",
            "pmc.example.gov/articles/PMC1/",
        ),
        ("i5", 5, SourceKind.STUDENT_PAPER, 1, True, "SYNTHETIC thesis by someone", None),
    ]
    extensions = report.extensions["compilatio"]
    assert extensions["source_groups"] == {
        "m1": "main",
        "m2": "main",
        "m3": "main",
        "i4": "incidental",
        "i5": "incidental",
    }
    assert extensions["source_origins"] == {"m2": "another_group", "i5": "my_library"}
    assert extensions["semantic_sources"] == ["m2"]
    assert extensions["mentioned_sources"] == ["https://www.example.com/cited"]


def test_reads_the_underlined_ai_passages() -> None:
    report = _parse(_report())
    assert report.ai_writing is not None
    assert [(s.page, s.text) for s in report.ai_writing.segments] == [
        (3, "este pasaje sintético que sigue en la línea siguiente."),
        (3, "Un segundo pasaje marcado."),
    ]
    assert any("from their underline" in w for w in report.warnings)


def test_personal_details_are_not_kept() -> None:
    content = dump_report(_parse(_report()))
    assert "NOMBRE INVENTADO" not in content
    assert "0000000000000000000000000000000000000000" not in content


def test_a_certificate_has_no_passages() -> None:
    summary = ["Certificado de análisis", *SUMMARY[1:]]
    report = _parse(_report(summary, body=False))
    assert report.extensions["compilatio"]["document"] == "certificate"
    assert report.ai_writing is not None
    assert report.ai_writing.segments == []
    assert report.similarity is not None
    assert len(report.similarity.sources) == 5
    assert any("analysis certificate" in w for w in report.warnings)


def test_ai_left_out_of_the_suspicious_percentage() -> None:
    ai = SUMMARY.index("Detección de IA")
    moved = SUMMARY[ai : ai + 3]
    summary = [*SUMMARY[:ai], *SUMMARY[ai + 3 :], *moved]
    summary[summary.index("Sintáctica 6% Semántica 7%")] = "Sintáctica 13% Semántica No medido"
    report = _parse(_report(summary))
    extensions = report.extensions["compilatio"]
    assert extensions["included_in_suspicious"] == {
        "similarity": True,
        "unrecognised_languages": True,
        "quoted": False,
        "ai": False,
    }
    assert extensions["semantic_similarity_percent"] is None
    assert any("not included in its suspicious-text" in w for w in report.warnings)


def test_missing_parts_are_warned_about() -> None:
    summary = [line for line in SUMMARY if line not in {"12%", "34%"}]
    pdf = _new()
    _summary(pdf, summary)
    page = _Page(pdf)
    page.text(45, 40, "Puntos de interés")
    page.text(124, 80, "Sin subrayados.", BLACK)
    report = _parse(bytes(pdf.output()))
    assert report.ai_writing is None
    warnings = " ".join(report.warnings)
    assert "No source table was found" in warnings
    assert "AI percentage could not be read" in warnings
    assert "suspicious_percent" not in report.extensions["compilatio"]
