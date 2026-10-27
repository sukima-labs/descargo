"""Functions the browser build calls. Each takes paths in Pyodide's in-memory file system
and plain values, and returns JSON text that the page parses.

A result is ``{"ok": true, ...}`` or ``{"ok": false, "error": "..."}`` for anything the
student can fix (an unreadable file, an invalid form). Programming errors are raised, so
the page shows them as unexpected.
"""

import hashlib
import json
import shutil
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from draftwitness.adapters import AdapterError, import_report
from draftwitness.core.data import data_dir
from draftwitness.core.documents import DocumentError, extract_text
from draftwitness.core.jurisdictions import PackError, load_pack, pack_ids, resolve_access_request
from draftwitness.core.profiles import (
    ProfileError,
    UnknownNodeError,
    find_profile,
    load_profile,
    profile_paths,
    unverified_facts,
)
from draftwitness.core.profiles.models import Node
from draftwitness.core.render.pdf import PdfMetadata, markdown_blocks, render_pdf
from draftwitness.core.report_schema import dump_report
from draftwitness.i18n import SUPPORTED_LOCALES, set_locale, tr
from draftwitness.modules.post.access_request import (
    TOOL_NAMES,
    AccessRequestError,
    AccessRequestInput,
    build_access_request,
    unlisted_profile,
)
from draftwitness.modules.post.audit import (
    AuditError,
    DeclarationsError,
    InputFile,
    load_declarations,
)
from draftwitness.modules.post.audit import audit as run_audit
from draftwitness.modules.post.audit import render_markdown as audit_markdown
from draftwitness.modules.post.audit.render import format_percent
from draftwitness.modules.pre.inspect import Level, inspect_file
from draftwitness.modules.pre.inspect import render_markdown as inspect_markdown

_workdirs: set[str] = set()


def _language(language: str) -> str:
    """The report and message language; also sets the interface locale for messages."""
    lang = language if language in SUPPORTED_LOCALES else "en"
    set_locale(lang)
    return lang


def _today(on: str | None) -> date:
    return date.fromisoformat(on) if on else date.today()


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def _document(*, title: str, markdown: str, stem: str, summary: list[str], **extra: object) -> str:
    """A rendered document: its Markdown, the same split into blocks for the page to draw
    (the blocks the PDF renderer draws), and any extra fields."""
    return json.dumps(
        {
            "ok": True,
            "title": title,
            "markdown": markdown,
            "blocks": markdown_blocks(markdown),
            "stem": stem,
            "summary": summary,
            **extra,
        },
        ensure_ascii=False,
    )


def _problems(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '(root)'}: {item['msg']}"
        for item in exc.errors()
    )


def workdir() -> str:
    """A fresh folder for one request's files; remove it with :func:`discard`."""
    path = tempfile.mkdtemp(prefix="draftwitness-")
    _workdirs.add(path)
    return path


def discard(path: str) -> None:
    """Delete a folder made by :func:`workdir`, with the student's files in it."""
    if path in _workdirs:
        shutil.rmtree(path, ignore_errors=True)
        _workdirs.discard(path)


def _paths(node: Node, prefix: str, label: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    children: list[Node] = [
        *getattr(node, "faculties", []),
        *getattr(node, "degrees", []),
        *getattr(node, "courses", []),
    ]
    for child in children:
        path = f"{prefix}/{child.id}" if prefix else child.id
        name = f"{label} \u203a {child.name}" if label else child.name
        found.append({"path": path, "label": name})
        found.extend(_paths(child, path, name))
    return found


def _countries() -> list[dict[str, object]]:
    """Jurisdiction packs a letter can be drafted with when the institution has no profile."""
    root = data_dir("jurisdictions")
    countries: list[dict[str, object]] = []
    for pack_id in pack_ids(root):
        try:
            languages = list(resolve_access_request(root, pack_id).template_files)
        except PackError:
            continue
        countries.append(
            {"id": pack_id, "name": load_pack(root, pack_id).name, "languages": languages}
        )
    return countries


def choices() -> str:
    """What the forms offer: the bundled institution profiles, with the
    faculty/degree/course paths of each; the countries whose packs can draft a letter for an
    institution with no profile; and the detector names a letter can mention."""
    root = data_dir("profiles")
    listed = []
    for path in profile_paths(root):
        profile = load_profile(path, root=root)
        listed.append(
            {
                "id": profile.id,
                "name": profile.institution.name,
                "country": profile.country,
                "unverified": len(unverified_facts(profile)),
                "paths": _paths(profile.institution, "", ""),
            }
        )
    return json.dumps(
        {"profiles": listed, "countries": _countries(), "tools": TOOL_NAMES}, ensure_ascii=False
    )


def inspect(path: str, language: str = "en", on: str | None = None) -> str:
    """``draftwitness inspect`` on one file."""
    lang = _language(language)
    file = Path(path)
    try:
        result = inspect_file(file, today=_today(on))
    except (OSError, DocumentError) as exc:
        return _error(f"{file.name}: {exc}")
    summary = tr(
        lang,
        "inspect.cli_summary",
        review=len(result.by_level(Level.REVIEW)),
        info=len(result.by_level(Level.INFO)),
        metadata=len(result.metadata),
    )
    return _document(
        title=tr(lang, "inspect.title"),
        markdown=inspect_markdown(result, lang),
        stem=f"inspection-{file.stem}",
        language=lang,
        summary=[summary],
        json=result.model_dump_json(indent=2) + "\n",
        subject=result.file.filename,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(
    report: str,
    document: str | None = None,
    declarations: str | None = None,
    profile: str | None = None,
    path: str | None = None,
    language: str = "en",
    on: str | None = None,
) -> str:
    """``draftwitness audit``; also returns the report itself as DraftWitness JSON, which is
    what ``draftwitness import-report`` writes."""
    lang = _language(language)
    today = _today(on)
    files = {
        role: Path(value)
        for role, value in (
            ("report", report),
            ("document", document),
            ("declarations", declarations),
        )
        if value
    }
    try:
        parsed = import_report(files["report"], parsed_at=datetime.now(UTC).replace(microsecond=0))
        text = extract_text(files["document"]) if "document" in files else None
        declared = load_declarations(files["declarations"]) if "declarations" in files else None
        chosen = find_profile(data_dir("profiles"), profile) if profile else None
        result = run_audit(
            parsed,
            today=today,
            document=text,
            declarations=declared,
            profile=chosen,
            path=path or None,
            inputs=[
                InputFile(role=role, filename=file.name, sha256=_sha256(file))
                for role, file in files.items()
            ],
        )
    except (
        OSError,
        AdapterError,
        DocumentError,
        DeclarationsError,
        ProfileError,
        UnknownNodeError,
        AuditError,
    ) as exc:
        return _error(str(exc))
    summary = tr(
        lang,
        "audit.summary",
        original=format_percent(result.overall_percent, lang),
        adjusted=format_percent(result.adjusted_percent, lang),
        method=tr(lang, f"audit.method_name_{result.method.value}"),
    )
    return _document(
        title=tr(lang, "audit.title"),
        markdown=audit_markdown(result, lang),
        stem=f"audit-{today.isoformat()}",
        language=lang,
        summary=[summary],
        warnings=list(parsed.warnings),
        json=result.model_dump_json(indent=2) + "\n",
        report_json=dump_report(parsed),
        report_stem=f"report-{files['report'].stem}",
        subject=result.submission_title,
    )


def access_request(  # noqa: PLR0913
    details: str,
    profile: str,
    path: str | None = None,
    language: str | None = None,
    interface: str = "en",
    on: str | None = None,
    *,
    jurisdiction: str | None = None,
    institution: str | None = None,
    office: str | None = None,
    office_email: str | None = None,
) -> str:
    """``draftwitness access-request``. ``details`` is the JSON form of the student YAML
    file; ``language`` is the letter's (default: the institution's), ``interface`` the
    language of messages. With an empty ``profile``, the letter is for ``institution`` in
    the country of pack ``jurisdiction``, optionally addressed to ``office``."""
    lang = _language(interface)
    today = _today(on)
    try:
        data = AccessRequestInput.model_validate(json.loads(details))
    except ValidationError as exc:
        return _error(_problems(exc))
    try:
        packs_root = data_dir("jurisdictions")
        chosen = (
            find_profile(data_dir("profiles"), profile)
            if profile
            else unlisted_profile(
                packs_root,
                jurisdiction or "",
                institution or "",
                office=office,
                office_email=office_email,
            )
        )
        document = build_access_request(
            chosen,
            data,
            packs_root=packs_root,
            today=today,
            path=path or None,
            language=language or None,
        )
    except (
        FileNotFoundError,
        ProfileError,
        UnknownNodeError,
        PackError,
        AccessRequestError,
    ) as exc:
        return _error(str(exc))
    return _document(
        title=document.title,
        markdown=document.markdown,
        stem=f"access-request-{today.isoformat()}",
        summary=[tr(lang, "access.review")],
        language=document.language,
        subject=f"{document.profile_id} / {document.jurisdiction}",
        warnings=[
            *([tr(lang, "access.no_recipient")] if document.recipient is None else []),
            *(
                [tr(lang, "access.unverified", count=len(document.unverified))]
                if document.unverified
                else []
            ),
            *document.unverified,
        ],
    )


def pdf(
    markdown: str,
    out: str,
    title: str,
    language: str,
    subject: str | None = None,
    on: str | None = None,
) -> str:
    """Render ``markdown`` as the CLI's PDF and write it to ``out``; returns ``out``."""
    today = _today(on)
    meta = PdfMetadata(
        title=title,
        language=language,
        created=datetime(today.year, today.month, today.day, tzinfo=UTC),
        subject=subject,
    )
    Path(out).write_bytes(render_pdf(markdown, meta))
    return out
