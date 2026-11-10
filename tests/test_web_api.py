import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from descargo import web
from descargo.core.data import DataFolder
from descargo.core.data import data_dir as bundled_data_dir
from descargo.core.profiles import load_profile
from descargo.i18n import DEFAULT_LOCALE, set_locale
from descargo.web import api
from descargo.web.api import _paths
from tests.conftest import FIXTURES
from tests.test_turnitin_ai_adapter import COVER as AI_COVER
from tests.test_turnitin_ai_adapter import OVERVIEW as AI_OVERVIEW
from tests.test_turnitin_ai_adapter import PAPER as AI_PAPER
from tests.test_turnitin_ai_adapter import _pdf as ai_pdf

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
    code = "import sys, descargo.web; sys.exit('typer' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0  # noqa: S603


def test_choices_lists_profiles_paths_and_tools() -> None:
    choices = _load(web.choices())
    by_id = {p["id"]: p for p in choices["profiles"]}
    assert set(by_id) == {"co/luisamigo", "es/uah", "us/utexas"}
    uah = by_id["es/uah"]
    assert uah["unverified"] > 0
    assert {"path": "escuela-doctorado", "label": "Escuela de Doctorado"} in uah["paths"]
    assert choices["tools"]["turnitin"] == "Turnitin"
    countries = {c["id"]: c for c in choices["countries"]}
    assert set(countries) == {"ar", "cl", "co", "es", "eu", "mx", "pe", "uk", "us"}
    assert countries["co"] == {"id": "co", "name": "Colombia", "languages": ["es"]}


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


def test_audit_of_a_turnitin_ai_writing_report(tmp_path: Path) -> None:
    pdf = tmp_path / "ai.pdf"
    pdf.write_bytes(ai_pdf(AI_COVER, AI_OVERVIEW, AI_PAPER))
    result = _load(web.audit(str(pdf), language="es", on=DAY))
    assert result["ok"] is True, result.get("error")
    assert result["title"] == "Resultado de escritura con IA"
    assert result["summary"] == [
        "Auditoría de un resultado de escritura con IA: la herramienta dice 23 %. No hay nada "
        "que descontar."
    ]
    assert "This sentence is highlighted as AI, and so is its second line." in result["markdown"]
    audit = json.loads(result["json"])
    assert (audit["overall_percent"], audit["method"]) == (None, None)
    assert json.loads(result["report_json"])["tool"]["report_kind"] == "ai_writing"
    assert any("parafraseado con IA" in warning for warning in result["warnings"])
    assert not any("could not" in warning for warning in result["warnings"])


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
    assert isinstance(result["warnings"], list)
    assert result["subject"] == "es/uah / es"


def test_access_request_warns_about_unverified_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    def data_dir(name: DataFolder) -> Path:
        return FIXTURES / "profiles" if name == "profiles" else bundled_data_dir(name)

    monkeypatch.setattr(api, "data_dir", data_dir)
    result = _load(web.access_request(json.dumps(DETAILS), "zz/synthetic-university", on=DAY))
    assert result["ok"] is True, result.get("error")
    assert result["warnings"][-2:] == [
        "1 fact(s) used in the letter still need verification:",
        "recipient contact",
    ]


def test_access_request_for_an_unlisted_institution() -> None:
    result = _load(
        web.access_request(
            json.dumps(DETAILS),
            "",
            interface="es",
            on=DAY,
            jurisdiction="co",
            institution="Instituto Sintético",
            office="Datos personales",
            office_email="datos@x.example",
        )
    )
    assert result["ok"] is True, result.get("error")
    assert result["subject"] == "co/other / co"
    assert "Instituto Sintético" in result["markdown"]
    assert result["warnings"][-1] == "contacto del destinatario"
    missing = _load(web.access_request(json.dumps(DETAILS), "", jurisdiction="co"))
    assert missing["ok"] is False
    assert missing["error"] == "Write the name of the institution."


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


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_web_demo_is_a_synthetic_report_that_audits_cleanly(language: str) -> None:
    demo = Path(__file__).parent.parent / "web" / "demo"
    result = _load(
        web.audit(
            str(demo / f"report-{language}.json"),
            document=str(demo / f"essay-{language}.md"),
            declarations=str(demo / f"declarations-{language}.yaml"),
            language=language,
            on=DAY,
        )
    )
    assert result["ok"] is True, result.get("error")
    audit = json.loads(result["json"])
    # The report says 47 %; quotes, the reference, the template and the declared earlier work
    # are discounted, and the rest stays. Both languages must agree.
    assert audit["overall_percent"] == 47
    assert 10 <= audit["adjusted_percent"] < 20
    assert "SYNTHETIC" in (demo / f"essay-{language}.md").read_text("utf-8").upper()
