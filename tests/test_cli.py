import subprocess
import sys

import pytest
import typer
from typer.testing import CliRunner

from descargo import __version__
from descargo.cli.app import app, main

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"descargo {__version__}"


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output
    assert "Not legal advice" in result.output


def _command_paths(command: object, prefix: tuple[str, ...] = ()) -> list[list[str]]:
    paths = [list(prefix)]
    for name, sub in getattr(command, "commands", {}).items():
        paths += _command_paths(sub, (*prefix, name))
    return paths


COMMANDS = _command_paths(typer.main.get_command(app))


def test_every_command_is_reached() -> None:
    assert {" ".join(p) for p in COMMANDS} >= {
        "access-request",
        "audit",
        "import-report",
        "inspect",
        "profile show",
        "profile unverified",
    }


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: " ".join(p) or "root")
def test_help_renders(path: list[str]) -> None:
    result = runner.invoke(app, [*path, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


def test_command_list_is_not_truncated() -> None:
    result = runner.invoke(app, ["--help"])
    commands = result.output.split("Commands:")[1]
    assert "..." not in commands
    assert "Draft a request for your detector report." in commands


def test_unknown_interface_language_is_a_usage_error() -> None:
    result = runner.invoke(app, ["--lang", "fr", "profile", "list"])
    assert result.exit_code == 2
    assert "'fr' is not one of 'en', 'es'" in result.output


def test_python_dash_m_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "descargo", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"descargo {__version__}"


def test_main_runs_the_app(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["descargo", "--version"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
