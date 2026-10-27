"""``draftwitness inspect``: report what a file contains besides its visible text."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer

from draftwitness.cli.common import check_targets, fail, parse_date
from draftwitness.core.documents import DocumentError
from draftwitness.core.render.pdf import PdfMetadata, render_pdf
from draftwitness.i18n import Locale, get_locale, t, tr
from draftwitness.modules.pre.inspect import Level, inspect_file, render_markdown


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
    output_format: Annotated[
        Literal["md", "json", "pdf"], typer.Option("--format", help="Output format.")
    ] = "md",
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write to this file instead of the terminal."),
    ] = None,
    language: Annotated[
        Locale | None,
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
    if output_format == "pdf" and out is None:
        raise fail(t("common.pdf_needs_out"))
    if out is not None:
        check_targets([out], inputs=[path], force=force)
    today = parse_date(on)
    try:
        result = inspect_file(path, today=today)
    except (OSError, DocumentError) as exc:
        raise fail(f"{path}: {exc}") from exc

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
    typer.echo(t("common.written", path=out))
    typer.echo(
        t(
            "inspect.cli_summary",
            review=len(result.by_level(Level.REVIEW)),
            info=len(result.by_level(Level.INFO)),
            metadata=len(result.metadata),
        )
    )
