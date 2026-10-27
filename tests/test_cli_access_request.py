from pathlib import Path

import pytest
from typer.testing import CliRunner

from draftwitness.cli.app import app
from draftwitness.i18n import DEFAULT_LOCALE, set_locale
from tests.conftest import REPO_ROOT

runner = CliRunner()
STUDENT = str(REPO_ROOT / "examples" / "student.example.yaml")


@pytest.fixture(autouse=True)
def _english() -> None:
    set_locale(DEFAULT_LOCALE)


def _run(*args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["--lang", "en", "access-request", *args])
    return result.exit_code, result.output


def test_writes_markdown_and_pdf(tmp_path: Path) -> None:
    out = tmp_path / "letters" / "uah"
    code, output = _run(
        "--profile", "es/uah", "--student", STUDENT, "--date", "2026-10-27", "--out", str(out)
    )
    assert code == 0, output
    assert out.with_suffix(".md").read_text().count("no es asesoramiento legal") >= 2
    assert out.with_suffix(".pdf").read_bytes().startswith(b"%PDF")
    assert "need verification" in output
    assert "DraftWitness sends nothing" in output


def test_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    out = str(tmp_path / "letter")
    args = ("--profile", "us/utexas", "--student", STUDENT, "--format", "md", "--out", out)
    assert _run(*args)[0] == 0
    code, output = _run(*args)
    assert code == 1
    assert "refusing to overwrite" in output
    assert _run(*args, "--force")[0] == 0


def test_pdf_only(tmp_path: Path) -> None:
    out = tmp_path / "letter"
    code, _ = _run(
        "--profile", "us/utexas", "--student", STUDENT, "--format", "pdf", "--out", str(out)
    )
    assert code == 0
    assert out.with_suffix(".pdf").exists()
    assert not out.with_suffix(".md").exists()


def test_default_output_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    code, _ = _run(
        "--profile", "es/uah", "--student", STUDENT, "--format", "md", "--date", "2026-10-27"
    )
    assert code == 0
    assert (tmp_path / "access-request-2026-10-27.md").exists()


def test_profile_without_recipient_warns(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles" / "zz"
    profiles.mkdir(parents=True)
    (profiles / "plain.yaml").write_text(
        'schema_version: "0.1"\nid: zz/plain\ncountry: ZZ\njurisdictions: [uk]\n'
        "languages: [en]\ninstitution: {id: plain, name: Plain University}\n"
    )
    code, output = _run(
        "--profile",
        "zz/plain",
        "--student",
        STUDENT,
        "--format",
        "md",
        "--profiles-dir",
        str(tmp_path / "profiles"),
        "--out",
        str(tmp_path / "x"),
    )
    assert code == 0, output
    assert "fill in the recipient" in output


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (("--format", "docx"), "unknown format"),
        (("--date", "27/10/2026"), "invalid --date"),
        (("--language", "fr"), "no 'fr' template"),
        (("--jurisdiction", "xx"), "no jurisdiction pack"),
        (("--path", "nope"), "no faculty"),
    ],
)
def test_errors(extra: tuple[str, ...], message: str, tmp_path: Path) -> None:
    code, output = _run(
        "--profile", "es/uah", "--student", STUDENT, "--out", str(tmp_path / "x"), *extra
    )
    assert code == 1
    assert message in output


def test_bad_student_file_and_unknown_profile(tmp_path: Path) -> None:
    bad = tmp_path / "student.yaml"
    bad.write_text("student: {name: Sam}\n")
    code, output = _run("--profile", "es/uah", "--student", str(bad))
    assert code == 1
    assert "email" in output
    code, output = _run("--profile", "xx/none", "--student", STUDENT)
    assert code == 1
