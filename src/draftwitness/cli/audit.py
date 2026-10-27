"""``draftwitness audit``: recompute a similarity percentage and explain each discount."""

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from draftwitness.core.data import data_dir
from draftwitness.core.documents import DocumentError, TextDocument, extract_text
from draftwitness.core.profiles import Profile, ProfileError, UnknownNodeError, find_profile
from draftwitness.core.render.pdf import PdfMetadata, render_pdf
from draftwitness.core.report_schema import Report, load_report
from draftwitness.i18n import get_locale, t, tr
from draftwitness.modules.post.audit import (
    AuditError,
    Declarations,
    DeclarationsError,
    InputFile,
    audit,
    load_declarations,
    render_markdown,
)
from draftwitness.modules.post.audit.render import format_percent

_FORMATS = ("md", "json", "pdf")


def _fail(message: str) -> typer.Exit:
    typer.echo(t("common.error", message=message), err=True)
    return typer.Exit(code=1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(
    report_path: Path,
    document_path: Path | None,
    declarations_path: Path | None,
) -> tuple[Report, TextDocument | None, Declarations | None]:
    try:
        report = load_report(report_path)
    except (OSError, ValidationError) as exc:
        raise _fail(f"{report_path}: {exc}") from exc
    try:
        document = extract_text(document_path) if document_path else None
    except (OSError, DocumentError) as exc:
        raise _fail(f"{document_path}: {exc}") from exc
    try:
        declarations = load_declarations(declarations_path) if declarations_path else None
    except DeclarationsError as exc:
        raise _fail(str(exc)) from exc
    return report, document, declarations


def audit_command(
    report_path: Annotated[
        Path,
        typer.Argument(
            metavar="REPORT",
            help="Report in DraftWitness JSON format.",
            exists=True,
            dir_okay=False,
        ),
    ],
    document_path: Annotated[
        Path | None,
        typer.Option(
            "--document",
            help="Your submitted work (.docx, .odt, .pdf, .txt or .md), to locate each match.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    declarations_path: Annotated[
        Path | None,
        typer.Option(
            "--declarations",
            help="YAML file declaring your own earlier work and institution templates "
            "(see examples/declarations.example.yaml).",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    profile_id: Annotated[
        str | None,
        typer.Option("--profile", help="Profile id, e.g. 'es/uah', to compare with its threshold."),
    ] = None,
    path: Annotated[
        str | None, typer.Option("--path", help="faculty[/degree[/course]] in the profile.")
    ] = None,
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
        str | None, typer.Option("--date", help="Audit date, YYYY-MM-DD. Defaults to today.")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
    profiles_dir: Annotated[
        Path | None, typer.Option("--profiles-dir", file_okay=False, exists=True)
    ] = None,
) -> None:
    """Recompute a similarity percentage after discounting quotations, references,
    templates and your declared own work, and explain every discount.

    Reads files on your device and writes only the output you ask for. It does not decide
    whether anything is plagiarism. Not legal advice.
    """
    if output_format not in _FORMATS:
        raise _fail(f"unknown format {output_format!r}")
    if output_format == "pdf" and out is None:
        raise _fail(t("audit.pdf_needs_out"))
    if out is not None and out.exists() and not force:
        raise _fail(t("access.exists", paths=str(out)))
    try:
        today = date.fromisoformat(on) if on else date.today()
    except ValueError as exc:
        raise _fail(f"invalid --date: {on}") from exc
    report, document, declarations = _load(report_path, document_path, declarations_path)
    profile: Profile | None = None
    if profile_id:
        try:
            profile = find_profile(profiles_dir or data_dir("profiles"), profile_id)
        except (FileNotFoundError, ProfileError) as exc:
            raise _fail(str(exc)) from exc
    inputs = [
        InputFile(role=role, filename=p.name, sha256=_sha256(p))
        for role, p in (
            ("report", report_path),
            ("document", document_path),
            ("declarations", declarations_path),
        )
        if p is not None
    ]
    try:
        result = audit(
            report,
            today=today,
            document=document,
            declarations=declarations,
            profile=profile,
            path=path,
            inputs=inputs,
        )
    except (AuditError, UnknownNodeError) as exc:
        raise _fail(str(exc)) from exc

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
            title=tr(lang, "audit.title"),
            language=lang,
            created=datetime(today.year, today.month, today.day, tzinfo=UTC),
            subject=result.submission_title,
        )
        out.write_bytes(render_pdf(content, meta))
    else:
        out.write_text(content, encoding="utf-8")
    typer.echo(t("audit.written", path=out))
    typer.echo(
        t(
            "audit.summary",
            original=format_percent(result.overall_percent, get_locale()),
            adjusted=format_percent(result.adjusted_percent, get_locale()),
            method=t(f"audit.method_name_{result.method.value}"),
        )
    )
