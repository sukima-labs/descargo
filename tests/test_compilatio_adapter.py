"""Compilatio PDF adapter, on synthetic PDFs that reproduce the lines and colours pypdf
extracts from a real Spanish Compilatio Magister report (read locally, never committed).
Every name, title and URL here is invented."""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fpdf import FPDF

from draftwitness.adapters import AdapterError, import_report
from draftwitness.adapters.compilatio import detect_layout, parse_pdf
from draftwitness.adapters.pdftext import pdf_lines
from draftwitness.core.render.pdf import _font_path
from draftwitness.core.report_schema import Report, SourceKind, dump_report

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
DARK = (33, 33, 33)
AI = (0, 191, 255)
BLACK = (0, 0, 0)
Line = str | tuple[tuple[int, int, int], str]

HEADER = [
    "INFORME DE ANÁLISIS",
    "magister",
    "SYNTHETIC Trabajo final",
    "64%",
    "Textos sospechosos",
    "12%Similitudes",
    "< 1 %similitudes entre comillas",
    "0 %entre las fuentes mencionadas",
    "1%Idiomas no reconocidos",
    "52%Textos potencialmente generados por la IA",
    "Nombre del documento:SYNTHETIC Trabajo final.docx",
    "ID del documento:0000000000000000000000000000000000000000",
    "Tamaño del documento original:12,5 kB",
    "Depositante:NOMBRE INVENTADO",
    "Fecha de depósito:05/10/2026",
    "Tipo de carga:interface",
    "fecha de fin de análisis:06/10/2026",
    "Número de palabras:1.234",
    "Número de caracteres:8.765",
    "Ubicación de las similitudes en el documento:",
    "Fuentes de similitudes",
]
MAIN = [
    "Fuentes principales detectadas",
    "N° Descripciones Similitudes Ubicaciones Datos adicionales",
    "1",
    "www.example.org",
    "https://www.example.org/a/very/long/path/that/the/report/shortens...",
    "2 fuentes similares",
    "8% Palabras idénticas:8%(99 palabras)",
    "2 docs.example.net | Synthetic page title – 20...https://docs.example.net/page "
    "< 1% Palabras idénticas:< 1%(12 palabras)",
]
INCIDENTAL = [
    "Fuentes con similitudes fortuitas",
    "N° Descripciones Similitudes Ubicaciones Datos adicionales",
    "1 Documento de otro usuario#abc123",
    "Viene de de otro grupo < 1% Palabras idénticas:< 1%(20 palabras)",
    "2 Synthetic Journal of Examples 2% Palabras idénticas:2%(25 palabras)",
]
MENTIONED = [
    "Fuentes mencionadas (sin similitudes detectadas) Estas fuentes han sido citadas en el "
    "documento sin encontrar similitudes.",
    "1 https://www.example.com/cited",
    "2 https://doi.org/10.0000/synthetic",
]
BODY: list[Line] = [
    "Puntos de interés",
    (BLACK, "1 www.example.org"),
    (DARK, "Introducción escrita por la persona autora."),
    (AI, "Este párrafo sintético aparece en el color"),
    (AI, "que Compilatio usa para la IA."),
    (DARK, "Una frase en el color normal."),
    (AI, "Un segundo pasaje marcado."),
]


def _pdf(*pages: Sequence[Line]) -> bytes:
    pdf = FPDF()
    pdf.set_creation_date(NOW)
    pdf.add_font("Liberation", fname=_font_path("LiberationSerif-Regular.ttf"))
    pdf.set_font("Liberation", size=8)
    for lines in pages:
        pdf.add_page()
        for line in lines:
            colour, text = line if isinstance(line, tuple) else (DARK, line)
            pdf.set_text_color(*colour)
            pdf.cell(text=text)
            pdf.ln()
    return bytes(pdf.output())


def _parse(data: bytes) -> Report:
    return parse_pdf(data, "informe.pdf", hashlib.sha256(data).hexdigest(), parsed_at=NOW)


def _report(*pages: Sequence[Line]) -> bytes:
    return _pdf(*(pages or ([*HEADER, *MAIN, *INCIDENTAL, *MENTIONED], BODY)))


def test_reads_results_sources_and_ai_passages() -> None:
    data = _report()
    report = _parse(data)
    assert report.tool.name == "compilatio"
    assert report.tool.product == "Compilatio Magister"
    assert report.tool.report_kind.value == "combined"
    assert report.provenance.adapter == "compilatio-pdf"
    assert report.submission.title == "SYNTHETIC Trabajo final"
    assert (report.submission.word_count, report.submission.character_count) == (1234, 8765)
    assert report.submission.submitted_at is None

    similarity = report.similarity
    assert similarity is not None
    assert similarity.overall_percent == 12
    rows = [
        (s.id, s.rank, s.kind, s.percent, s.percent_is_upper_bound, s.matched_words, s.url)
        for s in similarity.sources
    ]
    assert rows == [
        ("m1", 1, SourceKind.INTERNET, 8, False, 99, None),
        ("m2", 2, SourceKind.INTERNET, 1, True, 12, "https://docs.example.net/page"),
        ("i1", 1, SourceKind.STUDENT_PAPER, 1, True, 20, None),
        ("i2", 2, SourceKind.UNKNOWN, 2, False, 25, None),
    ]
    assert similarity.sources[1].label == "docs.example.net | Synthetic page title – 20..."
    assert similarity.matches == []

    ai = report.ai_writing
    assert ai is not None
    assert ai.overall_percent == 52
    assert [(s.page, s.text) for s in ai.segments] == [
        (2, "Este párrafo sintético aparece en el color que Compilatio usa para la IA."),
        (2, "Un segundo pasaje marcado."),
    ]

    extensions = report.extensions["compilatio"]
    assert extensions["source_groups"] == {
        "m1": "main",
        "m2": "main",
        "i1": "incidental",
        "i2": "incidental",
    }
    assert extensions["mentioned_sources"] == [
        "https://www.example.com/cited",
        "https://doi.org/10.0000/synthetic",
    ]
    assert (extensions["deposited_on"], extensions["analysed_on"]) == ("2026-10-05", "2026-10-06")
    assert extensions["suspicious_percent"] == 64
    assert extensions["quoted_percent_is_upper_bound"] is True
    assert extensions["unrecognised_languages_percent"] == 1
    assert any("from their colour" in w for w in report.warnings)


def test_personal_details_are_not_kept() -> None:
    content = dump_report(_parse(_report()))
    assert "NOMBRE INVENTADO" not in content
    assert "0000000000000000000000000000000000000000" not in content


def test_registry_picks_the_compilatio_adapter(tmp_path: Path) -> None:
    path = tmp_path / "informe.pdf"
    path.write_bytes(_report())
    assert import_report(path, parsed_at=NOW).tool.name == "compilatio"
    assert detect_layout(pdf_lines(_report())) == ("magister", "es")


def test_registry_names_what_it_can_read(tmp_path: Path) -> None:
    path = tmp_path / "other.pdf"
    path.write_bytes(_pdf(["ANALYSIS REPORT", "Some other detector"]))
    with pytest.raises(AdapterError, match="Compilatio analysis reports"):
        import_report(path, parsed_at=NOW)


def test_not_a_compilatio_report() -> None:
    with pytest.raises(AdapterError, match="not a Compilatio"):
        _parse(_pdf(["Something else"]))


def test_overall_similarity_is_required() -> None:
    header = [line for line in HEADER if line != "12%Similitudes"] + ["Similitudes"]
    with pytest.raises(AdapterError, match="overall similarity"):
        _parse(_pdf(header))


def test_bounds_odd_rows_and_missing_parts() -> None:
    header = [
        {"12%Similitudes": "3%Similitudes", "64%": "4%"}.get(line, line).replace(
            "05/10/2026", "31/02/2026"
        )
        for line in HEADER
        if "IA" not in line
    ]
    table = [
        "Fuentes principales detectadas",
        "1 www.example.org 5% Palabras idénticas:5%(9 palabras)",
        "1 www.example.org 5% Palabras idénticas:5%(9 palabras)",
        "no row here Palabras idénticas:1%(2 palabras)",
        "leftover text",
    ]
    report = _parse(_pdf([*header, *table], ["Cuerpo sin color de IA."]))
    assert report.ai_writing is None
    assert report.similarity is not None
    assert report.similarity.overall_percent == 3
    assert report.extensions["compilatio"]["deposited_on"] is None
    warnings = " ".join(report.warnings)
    for expected in (
        "more than the suspicious-text 4%",
        "appears twice",
        "was not understood",
        "not recognised as a source",
        "AI percentage could not be read",
    ):
        assert expected in warnings


def test_ai_percentage_without_coloured_passages() -> None:
    header = ["< 1 %Similitudes" if line == "12%Similitudes" else line for line in HEADER]
    report = _parse(_pdf(header, ["Nada en color."]))
    assert report.similarity is not None
    assert report.similarity.overall_percent == 1
    assert report.ai_writing is not None
    assert report.ai_writing.segments == []
    warnings = " ".join(report.warnings)
    assert "no passage drawn in Compilatio's AI colour" in warnings
    assert "No source table was found" in warnings
    assert "“<1%”" in warnings


def test_wrapped_labels_and_ignored_results() -> None:
    """The 2025 reports wrap long labels over several lines and may end a result in
    "(ignorado)"; their dates may have one-digit days and months."""
    header = [
        "INFORME DE ANÁLISIS",
        "magister",
        "SYNTHETIC Trabajo 16%Textos",
        "sospechosos",
        "16%Similitudes",
        "2%similitudes",
        "entre comillas",
        "< 1%entre las",
        "fuentes",
        "mencionadas",
        "0%Idiomas no",
        "reconocidos",
        "(ignorado)",
        "25%Textos",
        "potencialmente",
        "generados por",
        "la IA (ignorado)",
        "Nombre del documento:SYNTHETIC Trabajo con un nombre",
        "largo.docx",
        "ID del documento:0000000000000000000000000000000000000000",
        "Fecha de depósito:5/9/2025",
        "fecha de fin de análisis:5/9/2025",
        "Número de palabras:1.000",
    ]
    report = _parse(_pdf([*header, *MAIN], BODY))
    assert report.similarity is not None
    assert report.similarity.overall_percent == 16
    assert report.ai_writing is not None
    assert report.ai_writing.overall_percent == 25
    assert report.submission.title == "SYNTHETIC Trabajo con un nombre largo"
    extensions = report.extensions["compilatio"]
    assert extensions["marked_ignored"] == ["unrecognised_languages", "ai"]
    assert (extensions["suspicious_percent"], extensions["cited_percent"]) == (16, 1)
    assert extensions["deposited_on"] == "2025-09-05"
    assert any("“(ignorado)”" in w for w in report.warnings)
    assert not any("more than" in w for w in report.warnings)
