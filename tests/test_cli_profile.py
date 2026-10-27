import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from draftwitness.cli.app import app
from draftwitness.i18n import DEFAULT_LOCALE, set_locale
from tests.conftest import FIXTURES

runner = CliRunner()
SYNTHETIC_DIR = str(FIXTURES / "profiles")
INVALID_DIR = str(FIXTURES / "profiles_invalid")


@pytest.fixture(autouse=True)
def _english() -> None:
    set_locale(DEFAULT_LOCALE)


def test_list_bundled_profiles() -> None:
    result = runner.invoke(app, ["--lang", "en", "profile", "list"])
    assert result.exit_code == 0
    assert "es/uah\tUniversidad de Alcalá" in result.output
    assert "us/utexas" in result.output


def test_list_reports_invalid_and_empty_dirs(tmp_path: Path) -> None:
    result = runner.invoke(app, ["profile", "list", "--profiles-dir", INVALID_DIR])
    assert "INVALID" in result.output
    result = runner.invoke(app, ["profile", "list", "--profiles-dir", str(tmp_path)])
    assert "No profiles found" in result.output


def test_validate_bundled_profiles_pass() -> None:
    result = runner.invoke(app, ["profile", "validate"])
    assert result.exit_code == 0, result.output
    assert "0 invalid" in result.output


def test_validate_reports_problems_and_fails() -> None:
    result = runner.invoke(app, ["profile", "validate", "--profiles-dir", INVALID_DIR])
    assert result.exit_code == 1
    assert "verified fact needs source_url and checked_on" in result.output


def test_validate_explicit_files() -> None:
    path = str(FIXTURES / "profiles" / "zz" / "synthetic-university.yaml")
    result = runner.invoke(app, ["profile", "validate", path])
    assert result.exit_code == 0
    assert "1 valid" in result.output


def test_show_resolves_a_course_as_yaml() -> None:
    result = runner.invoke(
        app,
        [
            "profile",
            "show",
            "zz/synthetic-university",
            "--path",
            "science/biology/bio-thesis",
            "--profiles-dir",
            SYNTHETIC_DIR,
        ],
    )
    assert result.exit_code == 0, result.output
    document = yaml.safe_load(result.output)
    assert document["chain"][-1] == "bio-thesis"
    assert document["origins"]["ai_policy"] == ["bio-thesis"]


def test_show_json_and_errors() -> None:
    result = runner.invoke(app, ["profile", "show", "es/uah", "--format", "json"])
    assert json.loads(result.output)["profile"] == "es/uah"
    result = runner.invoke(app, ["profile", "show", "es/uah", "--format", "xml"])
    assert result.exit_code == 1
    result = runner.invoke(app, ["profile", "show", "es/uah", "--path", "nope"])
    assert result.exit_code == 1
    assert "no faculty 'nope'" in result.output
    result = runner.invoke(app, ["profile", "show", "xx/missing"])
    assert result.exit_code == 1


def test_unverified_lists_pending_facts_in_spanish() -> None:
    result = runner.invoke(
        app,
        [
            "--lang",
            "es",
            "profile",
            "unverified",
            "zz/synthetic-university",
            "--profiles-dir",
            SYNTHETIC_DIR,
        ],
    )
    assert result.exit_code == 0
    assert "pendientes de verificar" in result.output
    assert "institution.policies.similarity_thresholds[0]" in result.output


def test_unverified_all_and_fully_verified(tmp_path: Path) -> None:
    result = runner.invoke(app, ["profile", "unverified"])
    assert result.exit_code == 0
    assert "es/uah" in result.output
    assert "us/utexas" in result.output
    verified = tmp_path / "zz" / "verified.yaml"
    verified.parent.mkdir()
    verified.write_text(
        'schema_version: "0.1"\nid: zz/verified\ncountry: ZZ\njurisdictions: [eu]\n'
        "languages: [en]\ninstitution: {id: verified, name: Verified}\n"
    )
    result = runner.invoke(app, ["profile", "unverified", "--profiles-dir", str(tmp_path)])
    assert "every fact is verified" in result.output
    result = runner.invoke(
        app, ["profile", "unverified", "zz/none", "--profiles-dir", str(tmp_path)]
    )
    assert result.exit_code == 1
