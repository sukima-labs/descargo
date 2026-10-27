"""``draftwitness import-report``: turn a downloaded detector report into DraftWitness JSON."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from draftwitness.adapters import AdapterError, import_report
from draftwitness.cli.common import check_targets, fail
from draftwitness.core.report_schema import dump_report
from draftwitness.i18n import t


def import_report_command(
    path: Annotated[
        Path,
        typer.Argument(
            metavar="REPORT",
            help="The report you downloaded (for now, a Turnitin Similarity Report PDF).",
            exists=True,
            dir_okay=False,
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the JSON to this file instead of the terminal."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
) -> None:
    """Read a downloaded detector report into DraftWitness's report format (JSON).

    Records what the report says, with the SHA-256 of the file, and lists what could not be
    read. Drops the author name and file name shown on the report. The file is only read.
    """
    if out is not None:
        check_targets([out], inputs=[path], force=force)
    try:
        report = import_report(path, parsed_at=datetime.now(UTC).replace(microsecond=0))
    except (OSError, AdapterError) as exc:
        raise fail(f"{path}: {exc}") from exc
    content = dump_report(report)
    if out is None:
        typer.echo(content, nl=False)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        typer.echo(t("common.written", path=out))
    similarity = report.similarity
    if similarity is not None:
        typer.echo(
            t(
                "import.summary",
                tool=report.tool.product or report.tool.name,
                percent=f"{similarity.overall_percent:g}",
                sources=len(similarity.sources),
            ),
            err=out is None,
        )
    for warning in report.warnings:
        typer.echo(t("import.warning", text=warning), err=out is None)
