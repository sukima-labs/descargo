"""Root Typer application. Subcommands are registered here as each module lands."""

from typing import Annotated

import typer

from draftwitness import __version__

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
) -> None:
    """DraftWitness command-line interface."""


def main() -> None:
    """Console-script entry point."""
    app()
