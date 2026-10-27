import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from draftwitness.cli.app import app
from draftwitness.i18n import DEFAULT_LOCALE, set_locale
from tests.conftest import FIXTURES

runner = CliRunner()
AUDIT = FIXTURES / "audit"
REPORT = str(AUDIT / "report.json")
FULL = (
    REPORT,
    "--document",
    str(AUDIT / "essay.md"),
    "--declarations",
    str(AUDIT / "declarations.yaml"),
    "--date",
    "2026-10-27",
)


@pytest.fixture(autouse=True)
def _english() -> None:
    set_locale(DEFAULT_LOCALE)


def _run(*args: str, lang: str = "en") -> tuple[int, str]:
    result = runner.invoke(app, ["--lang", lang, "audit", *args])
    return result.exit_code, result.output


def test_markdown_to_terminal() -> None:
    code, output = _run(*FULL)
    assert code == 0, output
    assert output.startswith("# Similarity audit")
    assert "**Similarity after discounts:** 15.9%" in output
    assert "not legal advice" in output


def test_spanish_report() -> None:
    code, output = _run(*FULL, "--profile", "es/uah", "--path", "escuela-doctorado", lang="es")
    assert code == 0, output
    assert "**Similitud tras los descuentos:** 15,9 %" in output
    assert "Umbral orientativo" in output


def test_json_records_input_hashes() -> None:
    code, output = _run(*FULL, "--format", "json")
    assert code == 0, output
    data = json.loads(output)
    assert data["method"] == "exact"
    assert [item["role"] for item in data["inputs"]] == ["report", "document", "declarations"]
    assert all(len(item["sha256"]) == 64 for item in data["inputs"])


def test_pdf_and_overwrite_protection(tmp_path: Path) -> None:
    out = tmp_path / "audit" / "report.pdf"
    code, output = _run(*FULL, "--format", "pdf", "--out", str(out))
    assert code == 0, output
    assert out.read_bytes().startswith(b"%PDF")
    assert "after discounts 15.9% (exact)" in output
    code, output = _run(*FULL, "--format", "pdf", "--out", str(out))
    assert code == 1
    assert "refusing to overwrite" in output
    assert _run(*FULL, "--format", "md", "--out", str(out.with_suffix(".md")))[0] == 0


def test_inputs_are_not_modified(tmp_path: Path) -> None:
    before = {p: p.read_bytes() for p in AUDIT.iterdir()}
    assert _run(*FULL, "--out", str(tmp_path / "a.md"))[0] == 0
    assert {p: p.read_bytes() for p in AUDIT.iterdir()} == before


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--format", "pdf"), "--format pdf needs --out"),
        (("--date", "yesterday"), "invalid --date"),
        (("--profile", "xx/nowhere"), "xx/nowhere"),
        (("--profile", "es/uah", "--path", "no-such-faculty"), "no-such-faculty"),
    ],
)
def test_option_errors(args: tuple[str, ...], message: str) -> None:
    code, output = _run(REPORT, *args)
    assert code == 1
    assert message in output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--format", "docx"), "'docx' is not one of 'md', 'json', 'pdf'"),
        (("--language", "fr"), "'fr' is not one of 'en', 'es'"),
    ],
)
def test_usage_errors(args: tuple[str, ...], message: str) -> None:
    code, output = _run(REPORT, *args)
    assert code == 2
    assert message in output


@pytest.mark.parametrize("name", ["report.json", "essay.md", "declarations.yaml"])
def test_out_cannot_be_an_input(name: str, tmp_path: Path) -> None:
    for path in AUDIT.iterdir():
        (tmp_path / path.name).write_bytes(path.read_bytes())
    target = tmp_path / name
    before = target.read_bytes()
    code, output = _run(
        str(tmp_path / "report.json"),
        "--document",
        str(tmp_path / "essay.md"),
        "--declarations",
        str(tmp_path / "declarations.yaml"),
        "--out",
        str(target),
        "--force",
    )
    assert code == 1
    assert "must not be one of the input files" in output
    assert target.read_bytes() == before


def test_input_errors(tmp_path: Path) -> None:
    bad_report = tmp_path / "report.json"
    bad_report.write_text("{}", encoding="utf-8")
    code, output = _run(str(bad_report))
    assert code == 1
    assert "validation error" in output

    bad_document = tmp_path / "work.rtf"
    bad_document.write_text("x", encoding="utf-8")
    code, output = _run(REPORT, "--document", str(bad_document))
    assert code == 1
    assert "unsupported document type" in output

    bad_declarations = tmp_path / "declarations.yaml"
    bad_declarations.write_text("own_work: 3", encoding="utf-8")
    code, output = _run(REPORT, "--declarations", str(bad_declarations))
    assert code == 1
    assert "declarations.yaml" in output

    ai_only = str(FIXTURES / "reports" / "ai_writing_label_only.json")
    code, output = _run(ai_only)
    assert code == 1
    assert "no similarity section" in output
