import json
from datetime import date
from pathlib import Path

import pytest
import regex
from pypdf import PdfReader
from typer.testing import CliRunner

from draftwitness.cli.app import app
from draftwitness.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, catalog, set_locale
from draftwitness.modules.pre.inspect import (
    CodePoint,
    Finding,
    FindingKind,
    InspectedFile,
    Inspection,
    Level,
    Location,
    MetadataField,
    Occurrence,
    render_markdown,
)
from draftwitness.modules.pre.inspect.render import format_count, location_text

runner = CliRunner()
SAMPLE = "Title\n\nHello\u200bworld, plаgiarism.\nSecret" + "".join(
    chr(0xE0000 + ord(c)) for c in "hi"
)


@pytest.fixture(autouse=True)
def _english() -> None:
    set_locale(DEFAULT_LOCALE)


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    path = tmp_path / "essay.md"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def _run(*args: str, lang: str = "en") -> tuple[int, str]:
    result = runner.invoke(app, ["--lang", lang, "inspect", *args])
    return result.exit_code, result.output


def test_markdown_to_terminal(sample: Path) -> None:
    code, output = _run(str(sample), "--date", "2026-10-27")
    assert code == 0, output
    assert output.startswith("# Pre-submission inspection")
    assert "- Worth reviewing: 3" in output
    assert "### Tag characters (2)" in output
    assert "Decoded text: “hi”" in output
    assert "line 3: “Hello[U+200B]world, pl\u0430giarism.”" in output
    assert "27 October 2026" in output
    assert "not legal advice" in output


def test_spanish_report(sample: Path) -> None:
    code, output = _run(str(sample), "--date", "2026-10-27", lang="es")
    assert code == 0, output
    assert output.startswith("# Inspección previa a la entrega")
    assert "### Caracteres de etiqueta (2)" in output
    assert "línea 3" in output


def test_language_option_overrides_interface(sample: Path) -> None:
    code, output = _run(str(sample), "--language", "es")
    assert code == 0
    assert "Inspección previa" in output


def test_json_output(sample: Path, tmp_path: Path) -> None:
    out = tmp_path / "inspection.json"
    code, output = _run(str(sample), "--format", "json", "--out", str(out), "--date", "2026-10-27")
    assert code == 0, output
    assert "Written:" in output
    assert "Worth reviewing: 3 · for information: 0 · metadata fields: 0." in output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["inspection_format"] == "0.1"
    assert data["generated_on"] == "2026-10-27"
    assert data["file"]["filename"] == "essay.md"
    assert data["file"]["format"] == "text"
    assert {f["kind"] for f in data["findings"]} == {
        "format_characters",
        "tag_characters",
        "mixed_script_words",
    }
    Inspection.model_validate(data)


def test_pdf_output_is_deterministic(sample: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
    for out in (first, second):
        code, output = _run(
            str(sample), "--format", "pdf", "--out", str(out), "--date", "2026-10-27"
        )
        assert code == 0, output
    assert first.read_bytes() == second.read_bytes()
    reader = PdfReader(first)
    assert reader.metadata is not None
    assert reader.metadata.title == "Pre-submission inspection"
    assert "Tag characters" in reader.pages[0].extract_text()


def test_markdown_file_and_overwrite(sample: Path, tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    assert _run(str(sample), "--out", str(out))[0] == 0
    code, output = _run(str(sample), "--out", str(out))
    assert code == 1
    assert "refusing to overwrite" in output
    assert _run(str(sample), "--out", str(out), "--force")[0] == 0
    assert out.read_text(encoding="utf-8").startswith("# Pre-submission inspection")


def test_input_is_never_modified(sample: Path, tmp_path: Path) -> None:
    before = (sample.read_bytes(), sample.stat().st_mtime_ns)
    assert _run(str(sample), "--out", str(tmp_path / "r.md"))[0] == 0
    assert (sample.read_bytes(), sample.stat().st_mtime_ns) == before


def test_out_cannot_be_the_input(sample: Path) -> None:
    code, output = _run(str(sample), "--out", str(sample), "--force")
    assert code == 1
    assert "must not be one of the input files" in output
    assert sample.read_text(encoding="utf-8") == SAMPLE


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--format", "pdf"], "--format pdf needs --out"),
        (["--date", "yesterday"], "invalid --date"),
    ],
)
def test_option_errors(sample: Path, args: list[str], message: str) -> None:
    code, output = _run(str(sample), *args)
    assert code == 1
    assert message in output


def test_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "essay.docx"
    path.write_bytes(b"not a zip")
    code, output = _run(str(path))
    assert code == 1
    assert "not a ZIP-based document" in output


def test_findings_do_not_change_exit_status(tmp_path: Path) -> None:
    path = tmp_path / "plain.txt"
    path.write_text("Nothing unusual.", encoding="utf-8")
    code, output = _run(str(path))
    assert code == 0
    assert "Nothing in this file is likely to stand out" in output


# --- rendering ----------------------------------------------------------------------------


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_every_finding_kind_is_explained(locale: str) -> None:
    strings = catalog(locale)
    for kind in FindingKind:
        assert f"inspect.kind_{kind.value}" in strings, kind
        assert f"inspect.why_{kind.value}" in strings, kind


_ADVICE = {
    "en": regex.compile(r"\b(remove|strip|clean|delete|replace)\b", regex.IGNORECASE),
    "es": regex.compile(r"\b(elimina|quita|borra|limpia|sustituye|reemplaza)\b", regex.I),
}


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_report_never_advises_changing_the_file(locale: str) -> None:
    """ADR 006: the inspector describes; it never tells the student what to remove."""
    for key, text in catalog(locale).items():
        if key.startswith("inspect."):
            assert not _ADVICE[locale].search(text), key


def _inspection(findings: list[Finding], metadata: list[MetadataField]) -> Inspection:
    return Inspection(
        generated_on=date(2026, 10, 27),
        unidata_version="15.0.0",
        file=InspectedFile(filename="t.docx", sha256="0" * 64, size_bytes=123456, format="docx"),
        findings=findings,
        metadata=metadata,
        notes=["pdf_locked"],
    )


def test_render_details_locations_and_metadata() -> None:
    findings = [
        Finding(
            kind=FindingKind.FORMAT_CHARACTERS,
            level=Level.REVIEW,
            count=12,
            code_points=[CodePoint(code="U+200B", name="ZERO WIDTH SPACE", count=12)],
            occurrences=[
                Occurrence(location=Location(part="word/header2.xml", paragraph=3), text="a")
            ]
            * 10,
        ),
        Finding(
            kind=FindingKind.FIELDS,
            level=Level.INFO,
            count=3,
            details={"ADDIN ZOTERO_ITEM": 2, "PAGE": 1},
        ),
        Finding(
            kind=FindingKind.INCREMENTAL_UPDATES,
            level=Level.REVIEW,
            count=1,
            details={"eof_markers": 1200, "linearized": "no"},
        ),
    ]
    metadata = [MetadataField(part="docProps/core.xml", name="dc:creator", value="Student A")]
    text = render_markdown(_inspection(findings, metadata), "en")
    assert "**File:** t.docx (DOCX, 123,456 bytes)" in text
    assert "- Characters: U+200B ZERO WIDTH SPACE ×12" in text
    assert "  - header, paragraph 3: “a”" in text
    assert "Only the first 10 places are listed." in text
    assert "- Types: ADDIN ZOTERO_ITEM ×2, PAGE ×1" in text
    assert "- End-of-file markers: 1,200" in text
    assert "- Optimised for fast web view: no" in text
    assert "- **dc:creator** (docProps/core.xml): Student A" in text
    assert "encrypted and cannot be opened" in text
    spanish = render_markdown(_inspection(findings, metadata), "es")
    assert "123 456 bytes" in spanish
    assert "Optimizado para la vista web rápida: no" in spanish


def test_render_empty() -> None:
    text = render_markdown(_inspection([], []), "en")
    assert "Nothing in this file is likely to stand out" in text
    assert "Nothing to add." in text
    assert "No metadata fields were found." in text


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        (Location(part="word/document.xml", paragraph=2), "body, paragraph 2"),
        (Location(part="word/footer1.xml", paragraph=1), "footer, paragraph 1"),
        (Location(part="word/footnotes.xml"), "footnotes"),
        (Location(part="styles.xml", paragraph=4), "headers, footers or styles, paragraph 4"),
        (Location(part="custom/part.xml"), "custom/part.xml"),
        (Location(page=3), "page 3"),
        (Location(line=9), "line 9"),
        (Location(), "file"),
    ],
)
def test_location_text(location: Location, expected: str) -> None:
    assert location_text(location, "en") == expected


def test_format_count() -> None:
    assert format_count(1234567, "en") == "1,234,567"
    assert format_count(1234567, "es") == "1 234 567"
    assert format_count(12, "es") == "12"
