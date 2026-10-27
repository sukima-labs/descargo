from datetime import date
from pathlib import Path
from typing import Any

import pytest

from draftwitness.core.documents import extract_text, text_document
from draftwitness.core.profiles import Profile, find_profile
from draftwitness.core.report_schema import Report, load_report
from draftwitness.modules.post.access_request import NOT_LEGAL_ADVICE_MARKERS
from draftwitness.modules.post.audit import (
    AuditError,
    Declarations,
    DeclarationsError,
    DiscountRule,
    FindingKind,
    InputFile,
    Method,
    OwnWork,
    Template,
    audit,
    load_declarations,
    render_markdown,
)
from draftwitness.modules.post.audit.render import format_percent
from tests.conftest import FIXTURES, REPO_ROOT

AUDIT = FIXTURES / "audit"
TODAY = date(2026, 10, 27)


@pytest.fixture
def report() -> Report:
    return load_report(AUDIT / "report.json")


def _codes(result: Any) -> list[str]:
    return [note.code for note in result.notes]


def _report(similarity: dict[str, Any], word_count: int | None = 200) -> Report:
    return Report.model_validate(
        {
            "schema_version": "0.1",
            "tool": {"name": "turnitin", "report_kind": "similarity"},
            "provenance": {
                "adapter": "manual",
                "adapter_version": "0",
                "draftwitness_version": "0",
                "parsed_at": "2026-10-27T10:00:00Z",
            },
            "submission": {"word_count": word_count},
            "similarity": similarity,
        }
    )


def test_exact_audit_of_the_synthetic_essay(report: Report) -> None:
    result = audit(
        report,
        today=TODAY,
        document=extract_text(AUDIT / "essay.md"),
        declarations=load_declarations(AUDIT / "declarations.yaml"),
    )
    assert result.method is Method.EXACT
    assert result.overall_percent == 47
    assert result.located_percent == pytest.approx(47.09, abs=0.01)
    # 64 of 206 words discounted: 47 - (47.09 - 16.02)
    assert result.adjusted_percent == pytest.approx(15.93, abs=0.01)
    rules = {(d.rule, d.match_id or d.source_id) for d in result.discounts}
    assert rules == {
        (DiscountRule.TEMPLATE, "m0"),
        (DiscountRule.QUOTED_CITED, "m1"),
        (DiscountRule.BIBLIOGRAPHY, "m6"),
        (DiscountRule.OWN_WORK, "s2"),
    }
    quoted = next(d for d in result.discounts if d.rule is DiscountRule.QUOTED_CITED)
    assert quoted.citation == "(Smith, 2020, p. 47)"
    assert quoted.quotation_marks == "“…”"
    bibliography = next(d for d in result.discounts if d.rule is DiscountRule.BIBLIOGRAPHY)
    assert bibliography.heading == "References"
    findings = {(f.kind, f.match_id) for f in result.findings}
    assert findings == {
        (FindingKind.QUOTED_NOT_CITED, "m3"),
        (FindingKind.CITED_NOT_QUOTED, "m4"),
    }
    by_id = {row.id: row for row in result.sources}
    assert by_id["s5"].discounted_percent == 6  # capped at the source's own figure
    assert by_id["s6"].discounted_percent is None
    assert result.notes == []


def test_without_a_document_only_declarations_apply(report: Report) -> None:
    result = audit(report, today=TODAY, declarations=load_declarations(AUDIT / "declarations.yaml"))
    assert result.method is Method.APPROXIMATE
    # own work s2 (13) and the template passage m0 (13/206 words = 6.31, capped at s5's 6)
    assert result.adjusted_percent == 28
    assert result.denominator_words == 206
    assert {d.rule for d in result.discounts} == {DiscountRule.OWN_WORK, DiscountRule.TEMPLATE}
    assert "no_document" in _codes(result)


def test_nothing_to_discount(report: Report) -> None:
    result = audit(report, today=TODAY)
    assert result.method is Method.UNCHANGED
    assert result.adjusted_percent == 47


def test_exact_method_with_no_discount_is_unchanged() -> None:
    doc = text_document("alpha beta gamma delta epsilon zeta eta theta iota kappa")
    report = _report(
        {
            "overall_percent": 30,
            "sources": [{"id": "s1", "label": "x", "percent": 30}],
            "matches": [{"id": "m1", "source_id": "s1", "text": "alpha beta gamma"}],
        }
    )
    result = audit(report, today=TODAY, document=doc)
    assert result.method is Method.UNCHANGED
    assert result.located_percent == 30
    assert result.adjusted_percent == 30


def test_incomplete_match_list_falls_back_to_approximate(report: Report) -> None:
    data = report.model_dump(mode="json")
    data["similarity"]["matches"] = data["similarity"]["matches"][:2]
    result = audit(
        Report.model_validate(data), today=TODAY, document=extract_text(AUDIT / "essay.md")
    )
    assert result.method is Method.APPROXIMATE
    assert "matches_incomplete" in _codes(result)
    # template m0 is not declared here; only m1 (quoted and cited, 10/206 words) applies
    assert result.adjusted_percent == pytest.approx(47 - 4.85, abs=0.01)


def test_source_level_edge_cases() -> None:
    report = _report(
        {
            "overall_percent": 20,
            "filters": {},
            "sources": [
                {"id": "s1", "label": "Mine", "percent": 1, "percent_is_upper_bound": True},
                {"id": "s2", "label": "Brief", "matched_words": 20},
                {"id": "s3", "label": "Unknown size"},
            ],
            "matches": [{"id": "m1", "source_id": "s3"}],
        }
    )
    declarations = Declarations(
        own_work=[
            OwnWork(source="mine", description="My essay"),
            OwnWork(source="nope", description="x"),
        ],
        templates=[
            Template(source="s2", description="Brief"),
            Template(source="s1", description="dup"),
        ],
    )
    result = audit(report, today=TODAY, declarations=declarations)
    assert result.method is Method.APPROXIMATE
    assert result.adjusted_percent == 10  # 20 - 0 (upper bound) - 20 words / 200 words
    codes = _codes(result)
    assert "upper_bound" in codes
    assert "unknown_declared_source" in codes
    assert "filters_unknown" in codes
    rules = {d.source_id: d.rule for d in result.discounts}
    assert rules == {"s1": DiscountRule.OWN_WORK, "s2": DiscountRule.TEMPLATE}


def test_unquantified_span_discount() -> None:
    report = _report(
        {
            "overall_percent": 10,
            "sources": [{"id": "s1", "label": "Course page", "percent": 10}],
            "matches": [{"id": "m1", "source_id": "s1", "text": "submit before Friday"}],
        },
        word_count=None,
    )
    declarations = Declarations(
        templates=[Template(text="Submit before Friday.", description="Brief")]
    )
    result = audit(report, today=TODAY, declarations=declarations)
    assert result.method is Method.APPROXIMATE
    assert result.adjusted_percent == 10
    assert result.discounts[0].percent is None
    assert "unquantified" in _codes(result)


def test_not_located_and_ambiguous_and_fuzzy() -> None:
    doc = text_document(
        "Water leaves. Water leaves. Groundwater recharge happens mostly in wet years when "
        "soils stay saturated for several weeks in a row."
    )
    report = _report(
        {
            "overall_percent": 50,
            "sources": [{"id": "s1", "label": "x", "percent": 50}],
            "matches": [
                {"id": "m1", "source_id": "s1", "text": "water leaves"},
                {"id": "m2", "source_id": "s1", "text": "missing passage entirely"},
                {
                    "id": "m3",
                    "source_id": "s1",
                    "text": "Groundwater recharge happens mostly in wet years, when soils are "
                    "saturated for several weeks in a row",
                },
            ],
        }
    )
    result = audit(report, today=TODAY, document=doc)
    assert [f.kind for f in result.findings] == [FindingKind.NOT_LOCATED]
    codes = _codes(result)
    assert "ambiguous" in codes
    assert "fuzzy" in codes


def test_filter_mismatch_notes(report: Report) -> None:
    data = report.model_dump(mode="json")
    data["similarity"]["filters"] = {"quotes_excluded": True, "bibliography_excluded": True}
    result = audit(
        Report.model_validate(data), today=TODAY, document=extract_text(AUDIT / "essay.md")
    )
    codes = _codes(result)
    assert "quotes_filter_mismatch" in codes
    assert "bibliography_filter_mismatch" in codes


def test_ai_writing_only_report_cannot_be_audited() -> None:
    report = load_report(FIXTURES / "reports" / "ai_writing_label_only.json")
    with pytest.raises(AuditError, match="no similarity section"):
        audit(report, today=TODAY)


def test_thresholds_and_self_plagiarism_rule(report: Report) -> None:
    profile = find_profile(REPO_ROOT / "profiles", "es/uah")
    result = audit(
        report,
        today=TODAY,
        document=extract_text(AUDIT / "essay.md"),
        declarations=load_declarations(AUDIT / "declarations.yaml"),
        profile=profile,
        path="escuela-doctorado",
    )
    (check,) = result.thresholds
    assert (check.percent, check.original_exceeds, check.adjusted_exceeds) == (24, True, False)
    assert result.self_plagiarism_rule is not None

    institution = audit(report, today=TODAY, profile=profile)
    (none,) = institution.thresholds
    assert none.original_exceeds is None
    assert institution.self_plagiarism_rule is None  # no own-work discount, so not shown


def _profile(thresholds: list[dict[str, Any]]) -> Profile:
    return Profile.model_validate(
        {
            "id": "zz/mini",
            "country": "ZZ",
            "jurisdictions": ["eu"],
            "languages": ["en"],
            "institution": {
                "id": "mini",
                "name": "Mini University",
                "policies": {"similarity_thresholds": thresholds},
            },
        }
    )


@pytest.mark.parametrize("language", ["en", "es"])
def test_hard_threshold_and_profile_without_thresholds(report: Report, language: str) -> None:
    hard = _profile(
        [
            {
                "value": {"kind": "hard", "percent": 40},
                "source_url": "https://university.example/rule",
            }
        ]
    )
    result = audit(report, today=TODAY, profile=hard)
    (check,) = result.thresholds
    assert (check.original_exceeds, check.adjusted_exceeds) == (True, True)
    assert "40" in render_markdown(result, language)

    empty = audit(report, today=TODAY, profile=_profile([]))
    assert empty.thresholds == []
    assert "no_threshold_in_profile" in _codes(empty)


@pytest.mark.parametrize("language", ["en", "es"])
def test_render_contains_disclaimer_and_evidence(report: Report, language: str) -> None:
    result = audit(
        report,
        today=TODAY,
        document=extract_text(AUDIT / "essay.md"),
        declarations=load_declarations(AUDIT / "declarations.yaml"),
        profile=find_profile(REPO_ROOT / "profiles", "us/utexas"),
        inputs=[InputFile(role="report", filename="report.json", sha256="0" * 64)],
    )
    markdown = render_markdown(result, language)
    assert markdown.lower().count(NOT_LEGAL_ADVICE_MARKERS[language]) >= 2
    assert "(Smith, 2020, p. 47)" in markdown
    assert "SHA-256 " + "0" * 64 in markdown
    assert format_percent(47, language) in markdown
    assert "{" not in markdown


@pytest.mark.parametrize("language", ["en", "es"])
def test_render_approximate_and_empty(report: Report, language: str) -> None:
    approximate = audit(
        report, today=TODAY, declarations=load_declarations(AUDIT / "declarations.yaml")
    )
    text = render_markdown(approximate, language)
    assert "{" not in text
    unchanged = render_markdown(audit(report, today=TODAY), language)
    assert "{" not in unchanged
    no_words = _report(
        {
            "overall_percent": 10,
            "sources": [
                {"id": "s1", "label": "Mine", "percent": 1, "percent_is_upper_bound": True}
            ],
        },
        word_count=None,
    )
    result = audit(
        no_words,
        today=TODAY,
        declarations=Declarations(own_work=[OwnWork(source="s1", description="mine")]),
    )
    text = render_markdown(result, language)
    assert "{" not in text


def test_format_percent() -> None:
    assert format_percent(15.93, "es") == "15,9 %"
    assert format_percent(47.0, "en") == "47%"
    assert format_percent(1, "en", upper_bound=True) == "<1%"


def test_declarations_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Template(description="x", text="a", source="s1")
    path = tmp_path / "declarations.yaml"
    path.write_text("own_work: [{source: s1}]", encoding="utf-8")
    with pytest.raises(DeclarationsError, match="description"):
        load_declarations(path)
    path.write_text("templates: [{description: brief, file: missing.txt}]", encoding="utf-8")
    with pytest.raises(DeclarationsError, match=r"missing\.txt"):
        load_declarations(path)
    path.write_text("", encoding="utf-8")
    assert load_declarations(path) == Declarations()
