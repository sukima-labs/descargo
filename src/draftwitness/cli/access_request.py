"""``draftwitness access-request``: draft a request for access to detector reports."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer
import yaml
from pydantic import ValidationError

from draftwitness.cli.common import check_targets, fail, parse_date
from draftwitness.core.data import data_dir
from draftwitness.core.jurisdictions import PackError
from draftwitness.core.profiles import ProfileError, UnknownNodeError, find_profile
from draftwitness.core.render.pdf import PdfMetadata, render_pdf
from draftwitness.i18n import t
from draftwitness.modules.post.access_request import (
    AccessRequestError,
    AccessRequestInput,
    build_access_request,
)


def _load_input(path: Path) -> AccessRequestInput:
    try:
        return AccessRequestInput.model_validate(yaml.safe_load(path.read_text("utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise fail(f"{path}: {exc}") from exc


def access_request(
    profile_id: Annotated[str, typer.Option("--profile", help="Profile id, e.g. 'es/uah'.")],
    student: Annotated[
        Path,
        typer.Option(
            "--student",
            help="YAML file with your details and the work concerned "
            "(see examples/student.example.yaml).",
            exists=True,
            dir_okay=False,
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out", help="Output path without extension. Defaults to ./access-request-<date>."
        ),
    ] = None,
    output_format: Annotated[
        Literal["md", "pdf", "both"], typer.Option("--format", help="Output format.")
    ] = "both",
    path: Annotated[
        str | None, typer.Option("--path", help="faculty[/degree[/course]] in the profile.")
    ] = None,
    jurisdiction: Annotated[
        str | None,
        typer.Option(
            "--jurisdiction", help="Pack id. Defaults to the profile's most specific one."
        ),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option(
            "--language",
            help="Letter language, if the jurisdiction pack has a template in it. "
            "Defaults to the institution's.",
        ),
    ] = None,
    on: Annotated[
        str | None,
        typer.Option("--date", help="Letter date, YYYY-MM-DD. Defaults to today."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing files.")] = False,
    profiles_dir: Annotated[
        Path | None,
        typer.Option(
            "--profiles-dir",
            help="Folder with <country>/<institution>.yaml files. Defaults to the bundled ones.",
            file_okay=False,
            exists=True,
        ),
    ] = None,
    jurisdictions_dir: Annotated[
        Path | None,
        typer.Option(
            "--jurisdictions-dir",
            help="Folder with jurisdiction packs. Defaults to the bundled ones.",
            file_okay=False,
            exists=True,
        ),
    ] = None,
) -> None:
    """Draft a request for access to detector reports (GDPR, UK GDPR, FERPA, habeas data).

    Writes Markdown and/or PDF on your device. Nothing is sent: review the letter, then send
    it yourself. Not legal advice.
    """
    today = parse_date(on)
    data = _load_input(student)
    try:
        profile = find_profile(profiles_dir or data_dir("profiles"), profile_id)
        document = build_access_request(
            profile,
            data,
            packs_root=jurisdictions_dir or data_dir("jurisdictions"),
            today=today,
            path=path,
            jurisdiction=jurisdiction,
            language=language,
        )
    except (
        FileNotFoundError,
        ProfileError,
        UnknownNodeError,
        PackError,
        AccessRequestError,
    ) as exc:
        raise fail(str(exc)) from exc

    stem = out or Path(f"access-request-{today.isoformat()}")
    targets: list[Path] = []
    if output_format in {"md", "both"}:
        targets.append(stem.with_suffix(".md"))
    if output_format in {"pdf", "both"}:
        targets.append(stem.with_suffix(".pdf"))
    check_targets(targets, inputs=[student], force=force)
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".md":
            target.write_text(document.markdown, encoding="utf-8")
        else:
            meta = PdfMetadata(
                title=document.title,
                language=document.language,
                created=datetime(today.year, today.month, today.day, tzinfo=UTC),
                subject=f"{document.profile_id} / {document.jurisdiction}",
            )
            target.write_bytes(render_pdf(document.markdown, meta))
        typer.echo(t("common.written", path=target))
    if document.recipient is None:
        typer.echo(t("access.no_recipient"))
    if document.unverified:
        typer.echo(t("access.unverified", count=len(document.unverified)))
        for label in document.unverified:
            typer.echo(f"  - {label}")
    typer.echo(t("access.review"))
