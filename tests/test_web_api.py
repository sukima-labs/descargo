import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from draftwitness import web
from draftwitness.core.profiles import load_profile
from draftwitness.i18n import DEFAULT_LOCALE, set_locale
from draftwitness.web.api import _paths
from tests.conftest import FIXTURES

AUDIT = FIXTURES / "audit"
DAY = "2026-10-27"
DETAILS = {
    "student": {"name": "Alex Example", "email": "alex@student.example"},
    "request": {"submission_title": "The water cycle", "tools": ["turnitin"]},
}


@pytest.fixture(autouse=True)
def _english() -> None:
    set_locale(DEFAULT_LOCALE)


def _load(text: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(text)
    return result


def test_importing_the_web_api_does_not_import_the_cli() -> None:
    code = "import sys, draftwitness.web; sys.exit('typer' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0  # noqa: S603


def test_choices_lists_profiles_paths_and_tools() -> None:
    choices = _load(web.choices())
    by_id = {p["id"]: p for p in choices["profiles"]}
    assert set(by_id) == {"es/uah", "us/utexas"}
    uah = by_id["es/uah"]
    assert uah["unverified"] > 0
    assert {"path": "escuela-doctorado", "label": "Escuela de Doctorado"} in uah["paths"]
    assert choices["tools"]["turnitin"] == "Turnitin"


def test_paths_cover_every_level() -> None:
    profile = load_profile(FIXTURES / "profiles" / "zz" / "synthetic-university.yaml")
    assert _paths(profile.institution, "", "") == [
        {"path": "science", "label": "Faculty of Science"},
        {"path": "science/biology", "label": "Faculty of Science › BSc Biology"},
        {
            "path": "science/biology/bio-thesis",
            "label": "Faculty of Science › BSc Biology › Bachelor thesis in Biology",
        },
    ]


def test_inspect_returns_markdown_blocks_and_json() -> None:
    result = _load(web.inspect(str(AUDIT / "essay.md"), language="es", on=DAY))
    assert result["ok"] is True
    assert result["language"] == "es"
    assert result["title"] == "Inspección previa a la entrega"
    assert result["stem"] == "inspection-essay"
    assert result["blocks"][0] == ["h1", result["title"]]
    assert json.loads(result["json"])["generated_on"] == DAY
    assert result["summary"][0].startswith("Para revisar:")


def test_inspect_reports_an_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "essay.docx"
    path.write_bytes(b"not a zip")
    result = _load(web.inspect(str(path)))
    assert result == {"ok": False, "error": result["error"]}
    assert result["error"].startswith("essay.docx:")


def test_audit_matches_the_cli_figures() -> None:
    result = _load(
        web.audit(
            str(AUDIT / "report.json"),
            document=str(AUDIT / "essay.md"),
            declarations=str(AUDIT / "declarations.yaml"),
            profile="es/uah",
            on=DAY,
        )
    )
    assert result["ok"] is True, result.get("error")
    assert "**Similarity after discounts:** 15.9%" in result["markdown"]
    audit = json.loads(result["json"])
    assert [i["role"] for i in audit["inputs"]] == ["report", "document", "declarations"]
    assert audit["profile_id"] == "es/uah"
    assert json.loads(result["report_json"])["tool"]["name"] == "turnitin"
    assert result["report_stem"] == "report-report"
    assert result["stem"] == f"audit-{DAY}"


def test_audit_reports_problems_instead_of_raising(tmp_path: Path) -> None:
    bad = tmp_path / "report.json"
    bad.write_text("{}")
    assert _load(web.audit(str(bad)))["ok"] is False
    unknown = _load(web.audit(str(AUDIT / "report.json"), profile="es/uah", path="nowhere"))
    assert unknown["ok"] is False
    assert "nowhere" in unknown["error"]


def test_access_request_drafts_the_letter() -> None:
    result = _load(web.access_request(json.dumps(DETAILS), "es/uah", interface="es", on=DAY))
    assert result["ok"] is True, result.get("error")
    assert result["language"] == "es"
    assert "Alex Example" in result["markdown"]
    assert result["stem"] == f"access-request-{DAY}"
    assert result["summary"][0].startswith("Revisa el escrito")
    assert result["warnings"][0].startswith("2 dato(s)")
    assert result["subject"] == "es/uah / es"


def test_access_request_letter_language_can_be_chosen() -> None:
    result = _load(web.access_request(json.dumps(DETAILS), "es/uah", language="en", on=DAY))
    assert result["language"] == "en"


@pytest.mark.parametrize(
    ("details", "profile", "expected"),
    [
        ('{"student": {"name": ""}}', "es/uah", "student.name"),
        (json.dumps(DETAILS), "zz/none", "zz/none"),
    ],
)
def test_access_request_reports_problems(details: str, profile: str, expected: str) -> None:
    result = _load(web.access_request(details, profile))
    assert result["ok"] is False
    assert expected in result["error"]


def test_pdf_writes_the_file(tmp_path: Path) -> None:
    out = tmp_path / "letter.pdf"
    assert web.pdf("# Title\n\nText.", str(out), "Title", "en", subject="s", on=DAY) == str(out)
    assert out.read_bytes().startswith(b"%PDF-")


def test_workdir_and_discard() -> None:
    folder = Path(web.workdir())
    (folder / "essay.md").write_text("private")
    web.discard(str(folder))
    assert not folder.exists()


def test_discard_leaves_other_folders_alone(tmp_path: Path) -> None:
    keep = tmp_path / "keep"
    keep.mkdir()
    web.discard(str(keep))
    assert keep.is_dir()
    shutil.rmtree(keep)
