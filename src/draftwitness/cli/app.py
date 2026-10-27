"""Root Typer application. Subcommands are registered here as each module lands."""

from typing import Annotated

import typer

from draftwitness import __version__
from draftwitness.cli import access_request, audit, import_report, inspection, profile
from draftwitness.i18n import SUPPORTED_LOCALES, detect_locale, set_locale

app = typer.Typer(
    name="draftwitness",
    help=(
        "Local-first evidence toolkit for students facing plagiarism and AI-detector "
        "false positives. Nothing leaves your device. Not legal advice."
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"draftwitness {__version__}")
        raise typer.Exit


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
    lang: Annotated[
        str | None,
        typer.Option(
            "--lang",
            help=f"Interface language ({', '.join(SUPPORTED_LOCALES)}). "
            "Defaults to DRAFTWITNESS_LANG or the system locale.",
        ),
    ] = None,
) -> None:
    """DraftWitness command-line interface."""
    set_locale(detect_locale(lang))


app.add_typer(profile.app, name="profile")
app.command("access-request")(access_request.access_request)
app.command("import-report")(import_report.import_report_command)
app.command("audit")(audit.audit_command)
app.command("inspect")(inspection.inspect_command)


def main() -> None:
    """Console-script entry point."""
    app()
