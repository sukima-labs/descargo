"""``draftwitness audit``: recompute a similarity percentage and explain each discount."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer

from draftwitness.adapters import AdapterError, import_report
from draftwitness.cli.common import check_targets, fail, parse_date
from draftwitness.core.data import data_dir
from draftwitness.core.documents import DocumentError, TextDocument, extract_text
from draftwitness.core.profiles import Profile, ProfileError, UnknownNodeError, find_profile
from draftwitness.core.render.pdf import PdfMetadata, render_pdf
from draftwitness.core.report_schema import Report
from draftwitness.i18n import Locale, get_locale, t, tr
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(
    report_path: Path,
    document_path: Path | None,
    declarations_path: Path | None,
) -> tuple[Report, TextDocument | None, Declarations | None]:
    try:
        report = import_report(report_path, parsed_at=datetime.now(UTC).replace(microsecond=0))
    except (OSError, AdapterError) as exc:
        raise fail(f"{report_path}: {exc}") from exc
    try:
        document = extract_text(document_path) if document_path else None
    except (OSError, DocumentError) as exc:
        raise fail(f"{document_path}: {exc}") from exc
    try:
        declarations = load_declarations(declarations_path) if declarations_path else None
    except DeclarationsError as exc:
        raise fail(str(exc)) from exc
    return report, document, declarations


def audit_command(
    report_path: Annotated[
        Path,
        typer.Argument(
            metavar="REPORT",
            help="The detector report: a Turnitin Similarity Report or Compilatio analysis "
            "report PDF, or DraftWitness JSON.",
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
        str | None, typer.Option("--date", help="Audit date, YYYY-MM-DD. Defaults to today.")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
    profiles_dir: Annotated[
        Path | None,
        typer.Option(
            "--profiles-dir",
            help="Folder with <country>/<institution>.yaml files. Defaults to the bundled ones.",
            file_okay=False,
            exists=True,
        ),
    ] = None,
) -> None:
    """Recompute a similarity percentage after discounting quotations, references,
    templates and your declared own work, and explain every discount.

    Reads files on your device and writes only the output you ask for. It does not decide
    whether anything is plagiarism. Not legal advice.
    """
    if output_format == "pdf" and out is None:
        raise fail(t("common.pdf_needs_out"))
    if out is not None:
        check_targets([out], inputs=[report_path, document_path, declarations_path], force=force)
    today = parse_date(on)
    report, document, declarations = _load(report_path, document_path, declarations_path)
    profile: Profile | None = None
    if profile_id:
        try:
            profile = find_profile(profiles_dir or data_dir("profiles"), profile_id)
        except (FileNotFoundError, ProfileError) as exc:
            raise fail(str(exc)) from exc
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
        raise fail(str(exc)) from exc

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
    typer.echo(t("common.written", path=out))
    typer.echo(
        t(
            "audit.summary",
            original=format_percent(result.overall_percent, get_locale()),
            adjusted=format_percent(result.adjusted_percent, get_locale()),
            method=t(f"audit.method_name_{result.method.value}"),
        )
    )
