import subprocess
import sys

import pytest
from typer.testing import CliRunner

from draftwitness import __version__
from draftwitness.cli.app import app, main

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"draftwitness {__version__}"


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output
    assert "Not legal advice" in result.output


def test_python_dash_m_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "draftwitness", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"draftwitness {__version__}"


def test_main_runs_the_app(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["draftwitness", "--version"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
