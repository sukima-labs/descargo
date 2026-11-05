"""Root Typer application. Subcommands are registered here as each module lands."""

from typing import Annotated

import typer

from descargo import __version__
from descargo.cli import access_request, audit, import_report, inspection, profile
from descargo.i18n import Locale, detect_locale, set_locale

app = typer.Typer(
    name="descargo",
    help=(
        "Local-first evidence toolkit for students facing plagiarism and AI-detector "
        "false positives. Nothing leaves your device. Not legal advice."
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    # Plain help: Rich markup would read "faculty[/degree]" as a closing tag and crash.
    rich_markup_mode=None,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"descargo {__version__}")
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
        Locale | None,
        typer.Option(
            "--lang",
            help="Interface language. Defaults to DESCARGO_LANG or the system locale. "
            "Help texts and usage errors are in English.",
        ),
    ] = None,
) -> None:
    """Descargo command-line interface."""
    set_locale(detect_locale(lang))


# Short help is the one line shown in the command list; the docstring is the full help.
app.add_typer(profile.app, name="profile", short_help="List, validate and show profiles.")
app.command("access-request", short_help="Draft a request for your detector report.")(
    access_request.access_request
)
app.command("import-report", short_help="Read a detector report into JSON.")(
    import_report.import_report_command
)
app.command("audit", short_help="Recompute a similarity percentage.")(audit.audit_command)
app.command("inspect", short_help="List what a file holds besides its text.")(
    inspection.inspect_command
)


def main() -> None:
    """Console-script entry point."""
    app()
