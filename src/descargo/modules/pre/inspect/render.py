"""Render an :class:`Inspection` as a Markdown report in English or Spanish.

Every finding carries an explanation: what it is, common innocent causes, and what it does
not show. The report never tells the student to remove or change anything (ADR 006), and
ends with the "not legal advice" footer.
"""

from typing import Final

from descargo import __version__
from descargo.i18n import tr
from descargo.modules.post.access_request import format_date
from descargo.modules.pre.inspect.models import (
    MAX_OCCURRENCES,
    Finding,
    FindingKind,
    Inspection,
    Level,
    Location,
)

TIMES: Final = "\u00d7"
_PART_KEYS: Final = {
    "word/document.xml": "part_body",
    "word/footnotes.xml": "part_footnotes",
    "word/endnotes.xml": "part_endnotes",
    "word/comments.xml": "part_comments",
    "content.xml": "part_body",
    "styles.xml": "part_styles",
}


def format_count(value: int, language: str) -> str:
    """``12345`` as ``12,345`` (en) or ``12 345`` (es)."""
    text = f"{value:,}"
    return text.replace(",", tr(language, "inspect.thousands_separator"))


def location_text(location: Location, language: str) -> str:
    parts = []
    if location.part:
        name = location.part.rsplit("/", 1)[-1].removesuffix(".xml")
        key = _PART_KEYS.get(location.part)
        if key is None and name.startswith(("header", "footer")):
            key = "part_header" if name.startswith("header") else "part_footer"
        parts.append(tr(language, f"inspect.{key}") if key else location.part)
    for field in ("paragraph", "page", "line"):
        value = getattr(location, field)
        if value is not None:
            parts.append(tr(language, f"inspect.{field}", number=value))
    return ", ".join(parts) or tr(language, "inspect.part_file")


def _details(finding: Finding, language: str) -> list[str]:
    if finding.kind is FindingKind.FIELDS:
        types = ", ".join(f"{name} {TIMES}{count}" for name, count in finding.details.items())
        return [tr(language, "inspect.detail_field_types", value=types)]
    lines = []
    for key, value in finding.details.items():
        shown = format_count(value, language) if isinstance(value, int) else value
        if key in {"linearized", "opened_without_password"}:
            shown = tr(language, f"inspect.{value}")
        lines.append(tr(language, f"inspect.detail_{key}", value=shown))
    return lines


def _finding(finding: Finding, language: str) -> list[str]:
    kind = finding.kind.value
    count = format_count(finding.count, language)
    lines = [
        f"### {tr(language, f'inspect.kind_{kind}')} ({count})",
        "",
        tr(language, f"inspect.why_{kind}"),
        "",
    ]
    if finding.code_points:
        listed = ", ".join(
            f"{cp.code} {cp.name} {TIMES}{format_count(cp.count, language)}".replace("  ", " ")
            for cp in finding.code_points
        )
        lines.append("- " + tr(language, "inspect.code_points", value=listed))
    lines += [f"- {line}" for line in _details(finding, language)]
    if finding.occurrences:
        lines.append("- " + tr(language, "inspect.where"))
        for occurrence in finding.occurrences:
            where = location_text(occurrence.location, language)
            text = f": “{occurrence.text}”" if occurrence.text else ""
            lines.append(f"  - {where}{text}")
        listed_count = len(finding.occurrences)
        if finding.count > listed_count and listed_count == MAX_OCCURRENCES:
            lines.append("  - " + tr(language, "inspect.more", listed=MAX_OCCURRENCES))
    return lines


def _level(result: Inspection, level: Level, language: str) -> list[str]:
    findings = result.by_level(level)
    lines = [f"## {tr(language, f'inspect.level_{level.value}')}", ""]
    if not findings:
        return [*lines, tr(language, f"inspect.none_{level.value}")]
    for finding in findings:
        lines += [*_finding(finding, language), ""]
    return lines[:-1]


def _metadata(result: Inspection, language: str) -> list[str]:
    lines = [f"## {tr(language, 'inspect.metadata')}", ""]
    if not result.metadata:
        return [*lines, tr(language, "inspect.no_metadata")]
    lines += [tr(language, "inspect.metadata_intro"), ""]
    for field in result.metadata:
        lines.append(
            "- "
            + tr(
                language,
                "inspect.metadata_line",
                name=field.name,
                part=field.part,
                value=field.value,
            )
        )
    return lines


def _about(result: Inspection, language: str) -> list[str]:
    lines = [f"## {tr(language, 'inspect.about')}", ""]
    lines.append("- " + tr(language, "inspect.sha256", sha256=result.file.sha256))
    lines.append("- " + tr(language, "inspect.unidata", version=result.unidata_version))
    lines += ["- " + tr(language, f"inspect.note_{code}") for code in result.notes]
    lines.append("- " + tr(language, "inspect.levels_explained"))
    lines.append("- " + tr(language, "inspect.not_checked"))
    return lines


def render_markdown(result: Inspection, language: str) -> str:
    """The inspection as Markdown, ending with the "not legal advice" footer."""
    review = len(result.by_level(Level.REVIEW))
    info = len(result.by_level(Level.INFO))
    header = [
        f"# {tr(language, 'inspect.title')}",
        "",
        f"> {tr(language, 'inspect.intro')}",
        "",
        tr(
            language,
            "inspect.file_line",
            filename=result.file.filename,
            format=tr(language, f"inspect.format_{result.file.format}"),
            size=format_count(result.file.size_bytes, language),
            date=format_date(result.generated_on, language),
        ),
        "",
        f"## {tr(language, 'inspect.summary')}",
        "",
        "- " + tr(language, "inspect.summary_review", count=review),
        "- " + tr(language, "inspect.summary_info", count=info),
        "- " + tr(language, "inspect.summary_metadata", count=len(result.metadata)),
    ]
    sections = [
        header,
        _level(result, Level.REVIEW, language),
        _level(result, Level.INFO, language),
        _metadata(result, language),
        _about(result, language),
        ["---", "", tr(language, "documents.footer", version=__version__)],
    ]
    return "\n\n".join("\n".join(section) for section in sections) + "\n"
