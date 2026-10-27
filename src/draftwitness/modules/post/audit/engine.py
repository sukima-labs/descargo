"""Recompute a similarity percentage after discounting matches that are not plagiarism.

Implements ADR 005. The auditor applies stated rules and shows its evidence; it never
decides whether anything is or is not plagiarism, and it never hides the original figure.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict

from draftwitness import __version__
from draftwitness.core.documents import TextDocument, count_words
from draftwitness.core.facts import Verification
from draftwitness.core.profiles import Profile, resolve
from draftwitness.core.profiles.models import ThresholdKind
from draftwitness.core.report_schema import Report, Source
from draftwitness.core.report_schema.models import Match, SimilarityFilters
from draftwitness.modules.post.audit.declarations import Declarations
from draftwitness.modules.post.audit.locate import (
    LocateMethod,
    Location,
    Normalized,
    locate,
    normalize,
)
from draftwitness.modules.post.audit.rules import (
    AuditRules,
    bibliography_section,
    citation_near,
    enclosing_quotation,
    load_rules,
)

AUDIT_FORMAT_VERSION: Final = "0.1"
CONSISTENCY_TOLERANCE: Final = 2.0
"""Largest gap, in percentage points, between the report's overall figure and the figure
recomputed from located passages for the exact method to be used."""


class AuditError(ValueError):
    """The report cannot be audited."""


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DiscountRule(StrEnum):
    TEMPLATE = "template"
    BIBLIOGRAPHY = "bibliography"
    QUOTED_CITED = "quoted_cited"
    OWN_WORK = "own_work"


class Level(StrEnum):
    SPAN = "span"
    SOURCE = "source"


class FindingKind(StrEnum):
    QUOTED_NOT_CITED = "quoted_not_cited"
    CITED_NOT_QUOTED = "cited_not_quoted"
    NOT_LOCATED = "not_located"


class Method(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNCHANGED = "unchanged"


class Discount(_Out):
    rule: DiscountRule
    level: Level
    source_id: str
    source_label: str
    match_id: str | None = None
    words: int | None = None
    percent: float | None = None
    """Percentage points this discount accounts for; ``None`` if it cannot be quantified."""
    passage: str | None = None
    quotation_marks: str | None = None
    citation: str | None = None
    citation_style: str | None = None
    heading: str | None = None
    declaration: str | None = None
    """The student's declaration, verbatim."""


class Finding(_Out):
    """Something worth knowing that is reported but not discounted."""

    kind: FindingKind
    match_id: str
    source_id: str
    source_label: str
    passage: str | None = None
    citation: str | None = None


class SourceSummary(_Out):
    id: str
    label: str
    kind: str
    reported_percent: float | None
    upper_bound: bool
    discounted_percent: float | None
    rules: list[DiscountRule]


class ThresholdCheck(_Out):
    kind: ThresholdKind
    percent: float | None
    applies_to: str | None
    verification: Verification
    source_url: str | None
    original_exceeds: bool | None
    adjusted_exceeds: bool | None


class Note(_Out):
    """A remark rendered from the ``audit.note_<code>`` message, with ``params``."""

    code: str
    params: dict[str, str | int | float] = {}


class InputFile(_Out):
    role: str
    filename: str
    sha256: str


class AiPassage(_Out):
    page: int | None
    text: str
    words: int


class AiStatement(_Out):
    """The report's AI-writing result, as the tool states it. Nothing here is recomputed
    (ADR 009) until ADR 010 decides how DraftWitness explains it."""

    overall_percent: float | None
    label: str | None
    detector_model: str | None
    flagged_words: int | None
    """Words in the passages read from the report; ``None`` when none could be read."""
    passages: list[AiPassage]


def _ai_statement(report: Report) -> AiStatement | None:
    ai = report.ai_writing
    if ai is None:
        return None
    passages = [
        AiPassage(page=s.page, text=s.text, words=len(s.text.split()))
        for s in ai.segments
        if s.text
    ]
    return AiStatement(
        overall_percent=ai.overall_percent,
        label=ai.label,
        detector_model=ai.detector_model,
        flagged_words=sum(p.words for p in passages) if passages else None,
        passages=passages,
    )


class AuditResult(_Out):
    audit_format: str = AUDIT_FORMAT_VERSION
    draftwitness_version: str = __version__
    generated_on: date
    tool: str
    tool_product: str | None
    submission_title: str | None
    overall_percent: float
    adjusted_percent: float
    method: Method
    denominator_words: int | None
    document_words: int | None
    report_words: int | None
    located_percent: float | None
    """Overall figure recomputed from the passages DraftWitness located, before discounts."""
    filters: SimilarityFilters
    discounts: list[Discount]
    findings: list[Finding]
    sources: list[SourceSummary]
    profile_id: str | None = None
    profile_path: str | None = None
    thresholds: list[ThresholdCheck] = []
    self_plagiarism_rule: str | None = None
    self_plagiarism_source: str | None = None
    self_plagiarism_verification: Verification | None = None
    notes: list[Note] = []
    inputs: list[InputFile] = []
    ai_writing: AiStatement | None = None


@dataclass(frozen=True)
class _MatchContext:
    match_id: str
    source_id: str
    source_label: str
    words: int | None
    passage: str | None


def _find_source(sources: list[Source], reference: str) -> Source | None:
    for source in sources:
        if source.id == reference:
            return source
    wanted = reference.casefold()
    for source in sources:
        if source.label.casefold() == wanted:
            return source
    return None


def _union_words(document: TextDocument, spans: list[tuple[int, int]]) -> int:
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(count_words(document.text[start:end]) for start, end in merged)


def _percent(words: int, total: int | None) -> float | None:
    return round(words / total * 100, 2) if total else None


def _passage(text: str | None, limit: int = 240) -> str | None:
    if text is None:
        return None
    text = " ".join(text.replace("**", "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class _Auditor:
    def __init__(
        self,
        report: Report,
        document: TextDocument | None,
        declarations: Declarations,
        rules: AuditRules,
    ) -> None:
        if report.similarity is None:
            raise AuditError("the report has no similarity section")
        self.report = report
        self.similarity = report.similarity
        self.document = document
        self.declarations = declarations
        self.rules = rules
        self.sources = {s.id: s for s in self.similarity.sources}
        self.notes: list[Note] = []
        self.discounts: list[Discount] = []
        self.findings: list[Finding] = []
        self.located: dict[str, Location] = {}
        self.span_discounted: set[str] = set()
        self.source_rules: dict[str, tuple[DiscountRule, str]] = {}

    def note(self, code: str, **params: str | int | float) -> None:
        self.notes.append(Note(code=code, params=params))

    # Source-level declarations ---------------------------------------------------------

    def declare_sources(self) -> None:
        declared = [
            (DiscountRule.OWN_WORK, own.source, own.description)
            for own in self.declarations.own_work
        ]
        declared += [
            (DiscountRule.TEMPLATE, t.source, t.description)
            for t in self.declarations.templates
            if t.source
        ]
        for rule, reference, description in declared:
            source = _find_source(self.similarity.sources, reference)
            if source is None:
                self.note("unknown_declared_source", source=reference)
            elif source.id not in self.source_rules:
                self.source_rules[source.id] = (rule, description)

    # Span-level rules ------------------------------------------------------------------

    def _template_for(self, match: Match) -> str | None:
        if not match.text:
            return None
        needle = normalize(match.text).text.strip(" \"'")
        for template in self.declarations.templates:
            if template.text and needle and needle in normalize(template.text).text:
                return template.description
        return None

    def _locate(self, match: Match, source: Source, haystack: Normalized | None) -> Location | None:
        if haystack is None or not match.text:
            return None
        location = locate(match.text, haystack, near=match.start)
        if location is None:
            self.findings.append(
                Finding(
                    kind=FindingKind.NOT_LOCATED,
                    match_id=match.id,
                    source_id=source.id,
                    source_label=source.label,
                    passage=_passage(match.text),
                )
            )
            return None
        self.located[match.id] = location
        if location.occurrences > 1:
            self.note("ambiguous", match=match.id, count=location.occurrences)
        if location.method is LocateMethod.FUZZY:
            self.note("fuzzy", match=match.id, ratio=location.ratio)
        return location

    def examine_matches(self) -> None:
        document = self.document
        haystack = normalize(document.text) if document else None
        bibliography = bibliography_section(document, self.rules) if document else None
        for match in self.similarity.matches:
            source = self.sources[match.source_id]
            location = self._locate(match, source, haystack)
            if match.source_id in self.source_rules:
                continue
            passage = match.text
            if document is not None and location is not None:
                passage = document.text[location.start : location.end]
            context = _MatchContext(
                match_id=match.id,
                source_id=source.id,
                source_label=source.label,
                words=count_words(passage) if passage else match.word_count,
                passage=_passage(passage),
            )
            template = self._template_for(match)
            if template is not None:
                self._discount(DiscountRule.TEMPLATE, context, declaration=template)
                continue
            if document is None or location is None:
                continue
            if bibliography and bibliography.start <= location.start < bibliography.end:
                self._discount(DiscountRule.BIBLIOGRAPHY, context, heading=bibliography.heading)
                continue
            quotation = enclosing_quotation(document, location.start, location.end, self.rules)
            if quotation is not None:
                citation = citation_near(document, quotation.start, quotation.end, self.rules)
                if citation is not None:
                    self._discount(
                        DiscountRule.QUOTED_CITED,
                        context,
                        quotation_marks=quotation.marks,
                        citation=citation.text or None,
                        citation_style=citation.style,
                    )
                else:
                    self._finding(FindingKind.QUOTED_NOT_CITED, context)
                continue
            citation = citation_near(document, location.start, location.end, self.rules)
            if citation is not None:
                self._finding(FindingKind.CITED_NOT_QUOTED, context, citation=citation.text or None)

    def _discount(self, rule: DiscountRule, context: "_MatchContext", **extra: str | None) -> None:
        self.discounts.append(
            Discount(
                rule=rule,
                level=Level.SPAN,
                source_id=context.source_id,
                source_label=context.source_label,
                match_id=context.match_id,
                words=context.words,
                passage=context.passage,
                **extra,
            )
        )
        self.span_discounted.add(context.match_id)

    def _finding(
        self, kind: FindingKind, context: "_MatchContext", citation: str | None = None
    ) -> None:
        self.findings.append(
            Finding(
                kind=kind,
                match_id=context.match_id,
                source_id=context.source_id,
                source_label=context.source_label,
                passage=context.passage,
                citation=citation,
            )
        )

    # Computation -----------------------------------------------------------------------

    def _located_spans(self, matches: list[Match]) -> list[tuple[int, int]]:
        return [(self.located[m.id].start, self.located[m.id].end) for m in matches]

    def compute(self) -> tuple[Method, float, int | None, float | None]:
        overall = self.similarity.overall_percent
        matches = self.similarity.matches
        document = self.document
        located_percent = None
        if document is not None and matches and len(self.located) == len(matches):
            total = document.word_count
            located_percent = _percent(_union_words(document, self._located_spans(matches)), total)
            if (
                located_percent is not None
                and abs(located_percent - overall) <= CONSISTENCY_TOLERANCE
            ):
                return self._exact(total, located_percent)
            self.note("matches_incomplete", located=round(located_percent or 0, 1), overall=overall)
        method, adjusted, denominator = self._approximate()
        return method, adjusted, denominator, located_percent

    def _exact(self, total: int, located_percent: float) -> tuple[Method, float, int, float]:
        document = self.document
        if document is None:  # pragma: no cover - compute() checks this
            raise AuditError("the exact method needs the document")
        by_source: dict[str, list[Match]] = defaultdict(list)
        for match in self.similarity.matches:
            by_source[match.source_id].append(match)
        for source_id, (rule, declaration) in self.source_rules.items():
            words = _union_words(document, self._located_spans(by_source[source_id]))
            self._source_discount(source_id, rule, declaration, words, _percent(words, total))
        self.discounts = [
            d.model_copy(update={"percent": _percent(d.words or 0, total)})
            if d.level is Level.SPAN
            else d
            for d in self.discounts
        ]
        kept = [
            m
            for m in self.similarity.matches
            if m.id not in self.span_discounted and m.source_id not in self.source_rules
        ]
        if not self.discounts:
            return Method.UNCHANGED, self.similarity.overall_percent, total, located_percent
        kept_percent = _percent(_union_words(document, self._located_spans(kept)), total) or 0.0
        discounted_points = located_percent - kept_percent
        adjusted = round(max(0.0, self.similarity.overall_percent - discounted_points), 2)
        return Method.EXACT, adjusted, total, located_percent

    def _approximate(self) -> tuple[Method, float, int | None]:
        total = self.report.submission.word_count or (
            self.document.word_count if self.document else None
        )
        subtract = 0.0
        for source_id, (rule, declaration) in self.source_rules.items():
            source = self.sources[source_id]
            percent: float | None = None
            if source.percent is not None and not source.percent_is_upper_bound:
                percent = source.percent
            elif source.percent_is_upper_bound:
                self.note("upper_bound", source=source.label, bound=source.percent or 0)
            elif source.matched_words is not None:
                percent = _percent(source.matched_words, total)
            self._source_discount(source_id, rule, declaration, source.matched_words, percent)
            subtract += percent or 0.0
        per_source: dict[str, float] = defaultdict(float)
        updated: list[Discount] = []
        for discount in self.discounts:
            if discount.level is not Level.SPAN:
                updated.append(discount)
                continue
            percent = _percent(discount.words, total) if discount.words else None
            if percent is None:
                self.note("unquantified", match=discount.match_id or "")
            updated.append(discount.model_copy(update={"percent": percent}))
            per_source[discount.source_id] += percent or 0.0
        self.discounts = updated
        for source_id, points in per_source.items():
            source = self.sources[source_id]
            cap = source.percent if source.percent is not None else points
            subtract += min(points, cap)
        if not self.discounts:
            return Method.UNCHANGED, self.similarity.overall_percent, total
        adjusted = round(max(0.0, self.similarity.overall_percent - subtract), 2)
        return Method.APPROXIMATE, adjusted, total

    def _source_discount(
        self,
        source_id: str,
        rule: DiscountRule,
        declaration: str,
        words: int | None,
        percent: float | None,
    ) -> None:
        source = self.sources[source_id]
        self.discounts.append(
            Discount(
                rule=rule,
                level=Level.SOURCE,
                source_id=source_id,
                source_label=source.label,
                words=words,
                percent=percent,
                declaration=declaration,
            )
        )

    def source_summaries(self) -> list[SourceSummary]:
        rows: list[SourceSummary] = []
        for source in self.similarity.sources:
            mine = [d for d in self.discounts if d.source_id == source.id]
            points = [d.percent for d in mine if d.percent is not None]
            discounted = round(sum(points), 2) if points else None
            if discounted is not None and source.percent is not None:
                discounted = min(discounted, source.percent)
            rows.append(
                SourceSummary(
                    id=source.id,
                    label=source.label,
                    kind=source.kind.value,
                    reported_percent=source.percent,
                    upper_bound=source.percent_is_upper_bound,
                    discounted_percent=discounted,
                    rules=sorted({d.rule for d in mine}, key=list(DiscountRule).index),
                )
            )
        return rows

    def filter_notes(self) -> None:
        filters = self.similarity.filters
        rules = {d.rule for d in self.discounts}
        if filters.quotes_excluded is None and filters.bibliography_excluded is None:
            self.note("filters_unknown")
        if filters.quotes_excluded and DiscountRule.QUOTED_CITED in rules:
            self.note("quotes_filter_mismatch")
        if filters.bibliography_excluded and DiscountRule.BIBLIOGRAPHY in rules:
            self.note("bibliography_filter_mismatch")


def _threshold_checks(
    profile: Profile, path: str | None, overall: float, adjusted: float
) -> list[ThresholdCheck]:
    checks: list[ThresholdCheck] = []
    for fact in resolve(profile, path).policies.similarity_thresholds:
        threshold = fact.value
        limit = threshold.percent
        checks.append(
            ThresholdCheck(
                kind=threshold.kind,
                percent=limit,
                applies_to=threshold.applies_to,
                verification=fact.verification,
                source_url=fact.source_url,
                original_exceeds=None if limit is None else overall > limit,
                adjusted_exceeds=None if limit is None else adjusted > limit,
            )
        )
    return checks


def audit(
    report: Report,
    *,
    today: date,
    document: TextDocument | None = None,
    declarations: Declarations | None = None,
    profile: Profile | None = None,
    path: str | None = None,
    rules: AuditRules | None = None,
    inputs: list[InputFile] | None = None,
) -> AuditResult:
    """Audit ``report``. Pure function: it reads its arguments and writes nothing."""
    auditor = _Auditor(report, document, declarations or Declarations(), rules or load_rules())
    auditor.declare_sources()
    auditor.examine_matches()
    method, adjusted, total, located_percent = auditor.compute()
    auditor.filter_notes()
    if document is None:
        auditor.note("no_document")
    overall = auditor.similarity.overall_percent

    thresholds: list[ThresholdCheck] = []
    self_plagiarism = None
    if profile is not None:
        thresholds = _threshold_checks(profile, path, overall, adjusted)
        if not thresholds:
            auditor.note("no_threshold_in_profile")
        if any(d.rule is DiscountRule.OWN_WORK for d in auditor.discounts):
            self_plagiarism = resolve(profile, path).policies.self_plagiarism
    return AuditResult(
        generated_on=today,
        tool=report.tool.name,
        tool_product=report.tool.product,
        submission_title=report.submission.title,
        overall_percent=overall,
        adjusted_percent=adjusted,
        method=method,
        denominator_words=total,
        document_words=document.word_count if document else None,
        report_words=report.submission.word_count,
        located_percent=located_percent,
        filters=auditor.similarity.filters,
        discounts=auditor.discounts,
        findings=auditor.findings,
        sources=auditor.source_summaries(),
        profile_id=profile.id if profile else None,
        profile_path=path,
        thresholds=thresholds,
        self_plagiarism_rule=self_plagiarism.value if self_plagiarism else None,
        self_plagiarism_source=self_plagiarism.source_url if self_plagiarism else None,
        self_plagiarism_verification=self_plagiarism.verification if self_plagiarism else None,
        notes=auditor.notes,
        inputs=inputs or [],
        ai_writing=_ai_statement(report),
    )
