import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from draftwitness.cli.app import app
from draftwitness.core.report_schema import Report
from draftwitness.i18n import DEFAULT_LOCALE, set_locale
from tests.conftest import FIXTURES
from tests.test_turnitin_adapter import AUTHOR, _classic, _enhanced

runner = CliRunner()


@pytest.fixture(autouse=True)
def _english() -> None:
    set_locale(DEFAULT_LOCALE)


@pytest.fixture
def report_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "turnitin.pdf"
    path.write_bytes(_enhanced())
    return path


def _run(*args: str, lang: str = "en") -> tuple[int, str]:
    result = runner.invoke(app, ["--lang", lang, *args])
    return result.exit_code, result.output


def test_import_to_terminal(report_pdf: Path) -> None:
    result = runner.invoke(app, ["import-report", str(report_pdf)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    Report.model_validate(data)
    assert data["similarity"]["overall_percent"] == 24
    assert "Similarity Report: overall similarity 24%, 3 sources." in result.stderr
    assert "Note: Turnitin PDF reports show matched passages" in result.stderr
    assert AUTHOR not in result.stdout


def test_import_to_file_and_overwrite(report_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    code, output = _run("import-report", str(report_pdf), "--out", str(out))
    assert code == 0, output
    assert "Written:" in output
    assert Report.model_validate_json(out.read_bytes()).tool.name == "turnitin"
    code, output = _run("import-report", str(report_pdf), "--out", str(out))
    assert code == 1
    assert "refusing to overwrite" in output
    assert _run("import-report", str(report_pdf), "--out", str(out), "--force")[0] == 0


def test_out_cannot_be_the_report(report_pdf: Path) -> None:
    before = report_pdf.read_bytes()
    code, output = _run("import-report", str(report_pdf), "--out", str(report_pdf), "--force")
    assert code == 1
    assert "must not be one of the input files" in output
    assert report_pdf.read_bytes() == before


def test_import_spanish_summary(report_pdf: Path, tmp_path: Path) -> None:
    code, output = _run(
        "import-report", str(report_pdf), "--out", str(tmp_path / "r.json"), lang="es"
    )
    assert code == 0
    assert "similitud general 24 %, 3 fuentes." in output
    assert "Nota:" in output


def test_import_error(tmp_path: Path) -> None:
    path = tmp_path / "other.pdf"
    path.write_bytes(b"%PDF-1.4 garbage")
    code, output = _run("import-report", str(path))
    assert code == 1
    assert "cannot read PDF" in output


def test_import_json_passes_through() -> None:
    code, output = _run("import-report", str(FIXTURES / "reports" / "similarity_full.json"))
    assert code == 0
    assert json.loads(output.split("\nSimilarity")[0].split("\nFeedback Studio")[0])


def test_audit_reads_a_turnitin_pdf(tmp_path: Path) -> None:
    path = tmp_path / "turnitin.pdf"
    path.write_bytes(_classic())
    declarations = tmp_path / "declarations.yaml"
    declarations.write_text(
        "own_work:\n  - source: Submitted to Synthetic University\n"
        "    description: My own essay for an earlier course.\n",
        encoding="utf-8",
    )
    code, output = _run("audit", str(path), "--declarations", str(declarations), "--format", "json")
    assert code == 0, output
    data = json.loads(output)
    assert data["overall_percent"] == 10
    assert data["adjusted_percent"] == 8
    assert data["method"] == "approximate"
    assert data["inputs"][0]["filename"] == "turnitin.pdf"


def test_audit_reports_adapter_errors(tmp_path: Path) -> None:
    path = tmp_path / "turnitin.pdf"
    path.write_bytes(b"%PDF-1.4 garbage")
    code, output = _run("audit", str(path))
    assert code == 1
    assert "cannot read PDF" in output
