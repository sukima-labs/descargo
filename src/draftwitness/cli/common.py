"""Behaviour shared by every command: errors, dates and output files.

Exit status: 0 on success, 1 when DraftWitness refuses or cannot do what was asked (the
message says why), 2 for usage errors such as a missing file or an unknown option value.
"""

from collections.abc import Iterable
from datetime import date
from pathlib import Path

import typer

from draftwitness.i18n import t


def fail(message: str) -> typer.Exit:
    """Print ``message`` as an error and return the exit (status 1) for the caller to raise."""
    typer.echo(t("common.error", message=message), err=True)
    return typer.Exit(code=1)


def parse_date(value: str | None) -> date:
    """The ``--date`` option: an ISO date, or today when it is not given."""
    if value is None:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise fail(t("common.invalid_date", value=value)) from exc


def check_targets(targets: Iterable[Path], *, inputs: Iterable[Path | None], force: bool) -> None:
    """Refuse to write over an input file, even with ``--force``, or over any other existing
    file without it."""
    targets = list(targets)
    read = {p.resolve() for p in inputs if p is not None}
    for target in targets:
        if target.resolve() in read:
            raise fail(t("common.out_is_input", path=target))
    existing = [p for p in targets if p.exists()]
    if existing and not force:
        raise fail(t("common.exists", paths=", ".join(map(str, existing))))
