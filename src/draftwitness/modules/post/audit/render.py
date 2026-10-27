"""Render an :class:`AuditResult` as a Markdown report in English or Spanish.

The report is written for the student and for whoever they choose to show it to. It always
shows the original figure, every discount with its evidence, what was *not* discounted
and why, and the "not legal advice" statement (added here, not by a template).
"""

from draftwitness import __version__
from draftwitness.core.facts import Verification
from draftwitness.core.profiles.models import ThresholdKind
from draftwitness.i18n import tr
from draftwitness.modules.post.access_request import TOOL_NAMES, format_date
from draftwitness.modules.post.audit.engine import (
    AuditResult,
    Discount,
    DiscountRule,
    Finding,
    Level,
    Method,
    SourceSummary,
    ThresholdCheck,
)


def format_number(value: float, language: str) -> str:
    text = f"{value:.1f}".removesuffix(".0")
    return text.replace(".", tr(language, "audit.decimal_separator"))


def format_percent(value: float, language: str, *, upper_bound: bool = False) -> str:
    text = tr(language, "audit.percent", value=format_number(value, language))
    return f"<{text}" if upper_bound else text


def _points(value: float | None, language: str) -> str:
    if value is None:
        return tr(language, "audit.points_unknown")
    return tr(language, "audit.points", value=format_number(value, language))


def _flag(verification: Verification | None, language: str) -> str:
    if verification is Verification.NEEDS_VERIFICATION:
        return tr(language, "documents.note_flag_unverified")
    return ""


def _discount_lines(index: int, discount: Discount, language: str) -> list[str]:
    head = [f"**{tr(language, f'audit.rule_{discount.rule.value}')}**"]
    if discount.level is Level.SOURCE:
        head.append(tr(language, "audit.whole_source"))
    if discount.match_id:
        head.append(tr(language, "audit.match", id=discount.match_id))
    head.append(tr(language, "audit.source", id=discount.source_id, label=discount.source_label))
    if discount.words is not None:
        head.append(tr(language, "audit.words", count=discount.words))
    head.append(_points(discount.percent, language))
    lines = [f"{index}. {' · '.join(head)}"]
    if discount.passage:
        lines.append(f"   - {tr(language, 'audit.passage', text=discount.passage)}")
    if discount.rule is DiscountRule.QUOTED_CITED:
        citation = discount.citation or tr(language, "audit.note_reference")
        lines.append(
            "   - "
            + tr(
                language,
                "audit.evidence_quoted_cited",
                marks=discount.quotation_marks or "",
                citation=citation,
            )
        )
    elif discount.rule is DiscountRule.BIBLIOGRAPHY:
        lines.append(
            f"  - {tr(language, 'audit.evidence_bibliography', heading=discount.heading or '')}"
        )
    elif discount.declaration:
        key = "template" if discount.rule is DiscountRule.TEMPLATE else "own_work"
        lines.append(
            f"  - {tr(language, f'audit.evidence_{key}', declaration=discount.declaration)}"
        )
    return lines


def _finding_lines(finding: Finding, language: str) -> list[str]:
    head = [
        f"**{tr(language, f'audit.finding_{finding.kind.value}')}**",
        tr(language, "audit.match", id=finding.match_id),
        tr(language, "audit.source", id=finding.source_id, label=finding.source_label),
    ]
    lines = [f"- {' · '.join(head)}"]
    if finding.passage:
        lines.append(f"   - {tr(language, 'audit.passage', text=finding.passage)}")
    if finding.citation:
        lines.append(f"   - {tr(language, 'audit.citation_found', citation=finding.citation)}")
    lines.append(f"   - {tr(language, f'audit.finding_{finding.kind.value}_why')}")
    return lines


def _threshold_line(check: ThresholdCheck, result: AuditResult, language: str) -> str:
    flag = _flag(check.verification, language)
    applies = f" ({check.applies_to})" if check.applies_to else ""
    if check.kind is ThresholdKind.NONE_PUBLISHED or check.percent is None:
        text = tr(language, "audit.threshold_none", flag=flag)
    else:

        def side(exceeds: bool | None) -> str:
            return tr(language, "audit.above" if exceeds else "audit.at_or_below")

        text = tr(
            language,
            f"audit.threshold_{check.kind.value}",
            percent=format_percent(check.percent, language),
            applies=applies,
            original=format_percent(result.overall_percent, language),
            original_side=side(check.original_exceeds),
            adjusted=format_percent(result.adjusted_percent, language),
            adjusted_side=side(check.adjusted_exceeds),
            flag=flag,
        )
    if check.source_url:
        text += " " + tr(language, "audit.source_link", url=check.source_url)
    return f"- {text}"


def _source_line(row: SourceSummary, language: str) -> str:
    reported = (
        format_percent(row.reported_percent, language, upper_bound=row.upper_bound)
        if row.reported_percent is not None
        else tr(language, "audit.not_shown")
    )
    text = tr(
        language,
        "audit.source_row",
        id=row.id,
        label=row.label,
        kind=tr(language, f"audit.kind_{row.kind}"),
        reported=reported,
    )
    if row.rules:
        rules = ", ".join(tr(language, f"audit.rule_{rule.value}").lower() for rule in row.rules)
        text += "; " + tr(
            language,
            "audit.source_discounted",
            points=_points(row.discounted_percent, language),
            rules=rules,
        )
    return f"- {text}"


def _header(result: AuditResult, language: str) -> list[str]:
    tool = TOOL_NAMES.get(result.tool, result.tool)
    if result.tool_product:
        tool = f"{tool} ({result.tool_product})"
    title = result.submission_title or tr(language, "audit.untitled")
    lines = [
        f"# {tr(language, 'audit.title')}",
        "",
        f"> {tr(language, 'audit.intro')}",
        "",
        tr(
            language,
            "audit.report_line",
            tool=tool,
            title=title,
            date=format_date(result.generated_on, language),
        ),
        "",
        f"## {tr(language, 'audit.result')}",
        "",
        "- "
        + tr(language, "audit.reported", percent=format_percent(result.overall_percent, language)),
        "- "
        + tr(language, "audit.adjusted", percent=format_percent(result.adjusted_percent, language)),
        "- " + tr(language, f"audit.method_{result.method.value}"),
    ]
    if result.located_percent is not None:
        located = format_percent(result.located_percent, language)
        lines.append("- " + tr(language, "audit.located", percent=located))
    return lines


def _thresholds(result: AuditResult, language: str) -> list[str]:
    lines = [f"## {tr(language, 'audit.thresholds')}", ""]
    if result.profile_id is None:
        return [*lines, tr(language, "audit.no_profile")]
    where = result.profile_id + (f" ({result.profile_path})" if result.profile_path else "")
    lines += [tr(language, "audit.profile_line", profile=where), ""]
    lines += [_threshold_line(check, result, language) for check in result.thresholds]
    return [*lines, "", tr(language, "audit.percentage_not_misconduct")]


def _discounts(result: AuditResult, language: str) -> list[str]:
    lines = [f"## {tr(language, 'audit.discounts')}", ""]
    if not result.discounts:
        lines.append(tr(language, "audit.no_discounts"))
    for index, discount in enumerate(result.discounts, start=1):
        lines += _discount_lines(index, discount, language)
    if any(d.rule is DiscountRule.OWN_WORK for d in result.discounts):
        lines.append("")
        if result.self_plagiarism_rule:
            lines.append(
                tr(
                    language,
                    "audit.own_work_caveat_rule",
                    rule=result.self_plagiarism_rule,
                    url=result.self_plagiarism_source or "",
                    flag=_flag(result.self_plagiarism_verification, language),
                )
            )
        else:
            lines.append(tr(language, "audit.own_work_caveat"))
    return lines


def _findings(result: AuditResult, language: str) -> list[str]:
    lines = [f"## {tr(language, 'audit.not_discounted')}", ""]
    if not result.findings:
        lines.append(tr(language, "audit.no_findings"))
    for finding in result.findings:
        lines += _finding_lines(finding, language)
    return lines


def _method(result: AuditResult, language: str) -> list[str]:
    lines = [f"## {tr(language, 'audit.how')}", ""]
    if result.method is Method.EXACT:
        lines += [tr(language, "audit.how_exact", words=result.denominator_words or 0), ""]
    elif result.method is Method.APPROXIMATE:
        words = (
            tr(language, "audit.words", count=result.denominator_words)
            if result.denominator_words
            else tr(language, "audit.words_unknown")
        )
        lines += [tr(language, "audit.how_approximate", words=words), ""]
    lines.append(tr(language, "audit.rules_list"))
    lines += [f"- {tr(language, f'audit.rule_{rule.value}_explained')}" for rule in DiscountRule]
    return [*lines, f"- {tr(language, 'audit.rule_reported_only')}"]


def _inputs(result: AuditResult, language: str) -> list[str]:
    if not result.inputs:
        return []
    lines = [f"## {tr(language, 'audit.inputs')}", ""]
    for item in result.inputs:
        role = tr(language, f"audit.role_{item.role}")
        lines.append(
            "- "
            + tr(
                language, "audit.input_line", role=role, filename=item.filename, sha256=item.sha256
            )
        )
    return lines


def render_markdown(result: AuditResult, language: str) -> str:
    """The audit as Markdown, ending with the "not legal advice" footer."""
    sections = [
        _header(result, language),
        _thresholds(result, language),
        _discounts(result, language),
        _findings(result, language),
        [f"## {tr(language, 'audit.sources')}", ""]
        + [_source_line(row, language) for row in result.sources],
    ]
    if result.notes:
        sections.append(
            [f"## {tr(language, 'audit.notes')}", ""]
            + ["- " + tr(language, f"audit.note_{n.code}", **n.params) for n in result.notes]
        )
    sections.append(_method(result, language))
    if result.inputs:
        sections.append(_inputs(result, language))
    sections.append(["---", "", tr(language, "documents.footer", version=__version__)])
    return "\n\n".join("\n".join(section) for section in sections) + "\n"
