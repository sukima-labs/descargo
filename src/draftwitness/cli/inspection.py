"""``draftwitness inspect``: report what a file contains besides its visible text."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from draftwitness.core.documents import DocumentError
from draftwitness.core.render.pdf import PdfMetadata, render_pdf
from draftwitness.i18n import get_locale, t, tr
from draftwitness.modules.pre.inspect import Level, inspect_file, render_markdown

_FORMATS = ("md", "json", "pdf")


def _fail(message: str) -> typer.Exit:
    typer.echo(t("common.error", message=message), err=True)
    return typer.Exit(code=1)


def inspect_command(
    path: Annotated[
        Path,
        typer.Argument(
            metavar="FILE",
            help="The file you plan to submit (.docx, .odt, .pdf, .txt or .md).",
            exists=True,
            dir_okay=False,
        ),
    ],
    output_format: Annotated[str, typer.Option("--format", help="md, json or pdf.")] = "md",
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write to this file instead of the terminal."),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", help="Report language. Defaults to the interface language."),
    ] = None,
    on: Annotated[
        str | None,
        typer.Option("--date", help="Inspection date, YYYY-MM-DD. Defaults to today."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
) -> None:
    """List invisible or unusual characters, metadata, tracked changes, hidden text and
    other content of a file, with what each usually means.

    Reads the file and never changes it; it does not tell you what to change. The exit
    status is 0 whenever the file could be read, whatever it contains. Not legal advice.
    """
    if output_format not in _FORMATS:
        raise _fail(f"unknown format {output_format!r}")
    if output_format == "pdf" and out is None:
        raise _fail(t("inspect.pdf_needs_out"))
    if out is not None and out.exists() and not force:
        raise _fail(t("access.exists", paths=str(out)))
    if out is not None and out.resolve() == path.resolve():
        raise _fail(t("inspect.out_is_input"))
    try:
        today = date.fromisoformat(on) if on else date.today()
    except ValueError as exc:
        raise _fail(f"invalid --date: {on}") from exc
    try:
        result = inspect_file(path, today=today)
    except (OSError, DocumentError) as exc:
        raise _fail(f"{path}: {exc}") from exc

    lang = language or get_locale()
    if output_format == "json":
        content = result.model_dump_json(indent=2) + "\n"
    else:
        content = render_markdown(result, lang)
    if out is None:
        typer.echo(content, nl=False)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "pdf":
        meta = PdfMetadata(
            title=tr(lang, "inspect.title"),
            language=lang,
            created=datetime(today.year, today.month, today.day, tzinfo=UTC),
            subject=result.file.filename,
        )
        out.write_bytes(render_pdf(content, meta))
    else:
        out.write_text(content, encoding="utf-8")
    typer.echo(t("inspect.written", path=out))
    typer.echo(
        t(
            "inspect.cli_summary",
            review=len(result.by_level(Level.REVIEW)),
            info=len(result.by_level(Level.INFO)),
            metadata=len(result.metadata),
        )
    )
