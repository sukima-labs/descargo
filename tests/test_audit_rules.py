from pathlib import Path

import pytest
import yaml

from draftwitness.core.documents import TextDocument, text_document
from draftwitness.modules.post.audit.locate import LocateMethod, locate, normalize
from draftwitness.modules.post.audit.rules import (
    bibliography_section,
    citation_near,
    enclosing_quotation,
    load_rules,
)

RULES = load_rules()


def _span(doc: TextDocument, passage: str) -> tuple[int, int]:
    start = doc.text.index(passage)
    return start, start + len(passage)


# --- Patterns -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "style"),
    [
        ("(Smith, 2020, p. 47)", "author_year"),
        ("(García y López, 2019)", "author_year"),
        ("(Smith et al., 2020a; Doe, 2019)", "author_year"),
        ("(Álvarez, 2018, pág. 3)", "author_year"),
        ("(Ministerio de Educación, s. f.)", "author_undated"),
        ("(Smith, n.d.)", "author_undated"),
        ("Smith (2020)", "narrative"),
        ("García y López (2019, p. 12)", "narrative"),
        ("(Smith 23)", "mla"),
        ("(Smith and Lee 23-25)", "mla"),
        ("[12]", "numeric"),
        ("[3, 7]", "numeric"),
        ("[4–6]", "numeric"),
        ("¹²", "superscript"),
        ("Ibíd.", "note_abbreviation"),
        ("op. cit.", "note_abbreviation"),
        ("doi:10.1234/abc.567", "doi"),
    ],
)
def test_citation_patterns(text: str, style: str) -> None:
    pattern = next(c.pattern for c in RULES.citations if c.name == style)
    assert pattern.search(text), (style, text)


@pytest.mark.parametrize("text", ["(Table 3)", "(Figura 2)", "(in 2020 there were)", "(see above)"])
def test_non_citations(text: str) -> None:
    assert not any(c.pattern.search(text) for c in RULES.citations)


def test_vancouver_parenthetical_needs_a_preceding_quote_or_stop() -> None:
    pattern = next(c.pattern for c in RULES.citations if c.name == "numeric_parenthetical")
    assert pattern.search("“the basin”(3)")
    assert pattern.search("the basin. (3-5)")
    assert not pattern.search("step (3)")


def test_every_bundled_example_matches_its_pattern() -> None:
    path = Path(__file__).resolve().parent.parent / "src/draftwitness/modules/post/audit/rules.yaml"
    data = yaml.safe_load(path.read_text("utf-8"))
    for spec, compiled in zip(data["citations"], RULES.citations, strict=True):
        first = spec["example"].split(" · ")[0].split(" (typed")[0]
        assert compiled.pattern.search(first), spec["name"]


def test_load_rules_from_custom_file(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        "reference_headings: [quellen]\nquote_pairs: [['„', '“']]\ncitation_window: 10\n"
        "citations: [{name: n, example: '[1]', pattern: '\\[\\d\\]'}]\n",
        encoding="utf-8",
    )
    rules = load_rules(path)
    assert rules.reference_headings == frozenset({"quellen"})
    assert rules.quote_chars == frozenset({"„", "“"})


# --- Reference list -------------------------------------------------------------------------


def test_reference_list_last_heading_wins_and_appendix_ends_it() -> None:
    doc = text_document(
        "Contents\nReferences\n\nBody.\n\n## 7. References:\n\nSmith (2020).\n\n"
        "Appendix\n\nData.\n\n"
    )
    section = bibliography_section(doc, RULES)
    assert section is not None
    assert section.heading == "7. References:"
    assert doc.text[section.start : section.end].strip().endswith("Smith (2020).")


@pytest.mark.parametrize(
    "heading", ["Referencias bibliográficas", "**Bibliografía**", "VII. Works cited", "Fuentes."]
)
def test_reference_headings(heading: str) -> None:
    doc = text_document(f"Body.\n\n{heading}\n\nEntry.")
    section = bibliography_section(doc, RULES)
    assert section is not None
    assert section.end == doc.body_end


def test_no_reference_list() -> None:
    doc = text_document("Body text that mentions references in passing, not as a heading.")
    assert bibliography_section(doc, RULES) is None


# --- Quotations -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "marks"),
    [
        ("As she wrote, “the water leaves the basin” (Smith, 2020).", "“…”"),
        ("Como escribió, «the water leaves the basin» (Smith, 2020).", "«…»"),
        ('He said "the water leaves the basin" yesterday.', '"…"'),
        ("She wrote ‘the water leaves the basin’ once.", "‘…’"),
    ],
)
def test_enclosing_quotation(text: str, marks: str) -> None:
    doc = text_document(text)
    quotation = enclosing_quotation(doc, *_span(doc, "the water leaves the basin"), RULES)
    assert quotation is not None
    assert quotation.marks == marks


def test_span_that_includes_its_marks_is_still_quoted() -> None:
    doc = text_document("She wrote “the water leaves the basin.” Then left.")
    assert enclosing_quotation(doc, *_span(doc, "“the water leaves the basin.”"), RULES)


def test_not_quoted_cases() -> None:
    doc = text_document("The basin’s water leaves. “Another” the water leaves the basin “x”.")
    assert enclosing_quotation(doc, *_span(doc, "the water leaves the basin"), RULES) is None
    partly = text_document("“the water leaves” the basin")
    assert enclosing_quotation(partly, *_span(partly, "the water leaves” the basin"), RULES) is None
    straight = text_document('"one" and "two" the water leaves the basin')
    assert enclosing_quotation(straight, *_span(straight, "the water leaves"), RULES) is None
    unclosed = text_document("“the water leaves the basin")
    assert enclosing_quotation(unclosed, *_span(unclosed, "water leaves"), RULES) is None


def test_block_quotation() -> None:
    doc = text_document("Intro.\n\n> The water leaves the basin.\n\n(Smith, 2020, p. 4)")
    start, end = _span(doc, "water leaves")
    quotation = enclosing_quotation(doc, start, end, RULES)
    assert quotation is not None
    assert quotation.marks == "block"
    citation = citation_near(doc, quotation.start, quotation.end, RULES)
    assert citation is not None
    assert citation.text == "(Smith, 2020, p. 4)"


def test_quotation_outside_any_paragraph() -> None:
    doc = text_document("Text.")
    assert enclosing_quotation(doc, 50, 60, RULES) is None
    assert citation_near(doc, 50, 60, RULES) is None


# --- Citations ------------------------------------------------------------------------------


def test_citation_after_before_and_absent() -> None:
    after = text_document("“Water leaves” [4]. Other text.")
    found = citation_near(after, *_span(after, "“Water leaves”"), RULES)
    assert found is not None
    assert (found.text, found.style) == ("[4]", "numeric")

    before = text_document("Smith (2020) writes that “water leaves the basin”.")
    found = citation_near(before, *_span(before, "“water leaves the basin”"), RULES)
    assert found is not None
    assert found.style == "narrative"

    none = text_document("“Water leaves the basin” and nothing else here.")
    assert citation_near(none, *_span(none, "“Water leaves the basin”"), RULES) is None


def test_note_reference_counts_as_citation() -> None:
    plain = text_document("“Water leaves the basin.” Then.")
    doc = TextDocument(
        text=plain.text,
        paragraphs=plain.paragraphs,
        citation_marks=(plain.text.index(" Then"),),
        body_end=plain.body_end,
        source_format="docx",
    )
    found = citation_near(doc, *_span(doc, "“Water leaves the basin.”"), RULES)
    assert found is not None
    assert found.style == "note_reference"


# --- Locating passages ----------------------------------------------------------------------


def test_normalize_folds_quotes_dashes_case_and_hyphenation() -> None:
    normalized = normalize("“Evapo-\ntranspiration” — it’s­  HIGH")
    assert normalized.text == '"evapotranspiration" - it\'s high'
    assert len(normalized.index) == len(normalized.text)


def test_locate_exact_with_offset_hint() -> None:
    text = "the basin drains. Later, the basin drains again."
    haystack = normalize(text)
    first = locate("The basin drains", haystack)
    assert first is not None
    assert (first.start, first.occurrences, first.method) == (0, 2, LocateMethod.EXACT)
    near = locate("the basin drains", haystack, near=30)
    assert near is not None
    assert text[near.start : near.end] == "the basin drains"
    assert near.start > 20


def test_locate_fuzzy_and_misses() -> None:
    text = (
        "Groundwater recharge happens mostly in wet years when soils stay saturated for "
        "several weeks in a row."
    )
    passage = (
        "Groundwater recharge happens mostly in wet years, when soils are saturated for "
        "several weeks in a row"
    )
    location = locate(passage, normalize(text))
    assert location is not None
    assert location.method is LocateMethod.FUZZY
    assert location.ratio >= 0.85
    assert text[location.start : location.end].endswith("in a row")
    assert locate("not in the text at all", normalize(text)) is None
    assert locate("short miss", normalize(text)) is None
    assert locate(" “ ” ", normalize(text)) is None
