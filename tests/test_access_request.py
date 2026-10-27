import io
from datetime import UTC, date, datetime
from pathlib import Path

import pypdf
import pytest
import yaml

from draftwitness.core.data import data_dir
from draftwitness.core.jurisdictions import pack_ids, resolve_access_request
from draftwitness.core.profiles import find_profile, load_profile
from draftwitness.core.profiles.models import TimeUnit
from draftwitness.core.render.pdf import PdfMetadata, drawable, render_pdf
from draftwitness.modules.post.access_request import (
    NOT_LEGAL_ADVICE_MARKERS,
    AccessRequestError,
    AccessRequestInput,
    add_business_days,
    add_months,
    build_access_request,
    due_date,
    format_date,
    format_duration,
)
from tests.conftest import FIXTURES, REPO_ROOT

PACKS = data_dir("jurisdictions")
TODAY = date(2026, 10, 27)
SYNTHETIC = load_profile(FIXTURES / "profiles" / "zz" / "synthetic-university.yaml")
EXAMPLE = AccessRequestInput.model_validate(
    yaml.safe_load((REPO_ROOT / "examples" / "student.example.yaml").read_text())
)
MINIMAL = AccessRequestInput.model_validate(
    {"student": {"name": "Sam Synthetic", "email": "sam@student.example"}}
)
ALL_TEMPLATES = [
    (pack_id, language)
    for pack_id in pack_ids(PACKS)
    for language in resolve_access_request(PACKS, pack_id).template_files
]


@pytest.mark.parametrize(("pack_id", "language"), ALL_TEMPLATES)
@pytest.mark.parametrize("data", [EXAMPLE, MINIMAL], ids=["full", "minimal"])
def test_every_template_renders_with_disclaimer(
    pack_id: str, language: str, data: AccessRequestInput
) -> None:
    document = build_access_request(
        SYNTHETIC, data, packs_root=PACKS, today=TODAY, jurisdiction=pack_id, language=language
    )
    text = document.markdown.lower()
    marker = NOT_LEGAL_ADVICE_MARKERS[language]
    assert text.count(marker) >= 2, "note and footer must both carry the disclaimer"
    assert document.markdown.rstrip().endswith(".")  # footer is last
    assert data.student.name in document.markdown
    assert "{{" not in document.markdown
    assert "{%" not in document.markdown
    assert "\\\n\n" not in document.markdown  # no dangling hard break
    assert document.title


def test_uah_letter_uses_profile_and_pack_data() -> None:
    profile = find_profile(data_dir("profiles"), "es/uah")
    document = build_access_request(profile, EXAMPLE, packs_root=PACKS, today=TODAY)
    assert document.language == "es"
    assert document.jurisdiction == "es"
    assert document.recipient is not None
    assert document.recipient.email == "protecciondedatos@uah.es"
    assert "LOPDGDD" in document.markdown
    assert "27 de noviembre de 2026" in document.markdown  # one month after sending
    assert "Turnitin" in document.markdown
    assert "Alex Example (DNI" not in document.markdown  # no identity document given


def test_tools_default_to_the_profile() -> None:
    document = build_access_request(SYNTHETIC, MINIMAL, packs_root=PACKS, today=TODAY)
    assert "Turnitin" in document.markdown


def test_extra_items_are_numbered_after_the_standard_ones() -> None:
    data = AccessRequestInput.model_validate(
        {
            "student": {"name": "Sam Synthetic", "email": "sam@student.example"},
            "request": {"extra_items": ["The instructor's grading rubric."]},
        }
    )
    document = build_access_request(
        SYNTHETIC, data, packs_root=PACKS, today=TODAY, jurisdiction="eu", language="en"
    )
    assert "6. The instructor's grading rubric." in document.markdown


def test_missing_recipient_leaves_a_placeholder() -> None:
    profile = SYNTHETIC.model_copy(
        update={
            "institution": SYNTHETIC.institution.model_copy(
                update={
                    "policies": SYNTHETIC.institution.policies.model_copy(update={"contacts": []})
                }
            )
        }
    )
    document = build_access_request(
        profile, MINIMAL, packs_root=PACKS, today=TODAY, jurisdiction="uk"
    )
    assert document.recipient is None
    assert "[Data Protection Officer]" in document.markdown
    assert "no suitable contact" in document.markdown


def test_unverified_facts_are_reported() -> None:
    document = build_access_request(
        SYNTHETIC, MINIMAL, packs_root=PACKS, today=TODAY, jurisdiction="co"
    )
    assert "recipient contact" in document.unverified  # synthetic DPO is unverified
    assert f"{len(document.unverified)} dato(s)" in document.markdown


def test_colombia_prerequisite_and_business_days() -> None:
    document = build_access_request(
        SYNTHETIC, MINIMAL, packs_root=PACKS, today=TODAY, jurisdiction="co"
    )
    assert "agotar la consulta" in document.markdown
    assert "10 días hábiles" in document.markdown
    assert "10 de noviembre de 2026" in document.markdown  # 10 weekdays after 27 Oct


def test_language_selection() -> None:
    with pytest.raises(AccessRequestError, match="available: en"):
        build_access_request(
            SYNTHETIC, MINIMAL, packs_root=PACKS, today=TODAY, jurisdiction="us", language="es"
        )
    us_only_spanish = SYNTHETIC.model_copy(update={"languages": ["es"]})
    document = build_access_request(
        us_only_spanish, MINIMAL, packs_root=PACKS, today=TODAY, jurisdiction="us"
    )
    assert document.language == "en"  # first available template


@pytest.mark.parametrize(
    ("start", "amount", "unit", "expected"),
    [
        (date(2026, 10, 30), 1, TimeUnit.BUSINESS_DAYS, date(2026, 11, 2)),  # Fri → Mon
        (date(2026, 10, 27), 10, TimeUnit.BUSINESS_DAYS, date(2026, 11, 10)),
        (date(2026, 1, 31), 1, TimeUnit.MONTHS, date(2026, 2, 28)),
        (date(2026, 11, 30), 3, TimeUnit.MONTHS, date(2027, 2, 28)),
        (date(2026, 10, 27), 45, TimeUnit.CALENDAR_DAYS, date(2026, 12, 11)),
    ],
)
def test_due_dates(start: date, amount: int, unit: TimeUnit, expected: date) -> None:
    assert due_date(start, amount, unit) == expected


def test_date_helpers() -> None:
    assert add_business_days(date(2026, 10, 31), 1) == date(2026, 11, 2)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert format_date(TODAY, "en") == "27 October 2026"
    assert format_date(TODAY, "es") == "27 de octubre de 2026"
    assert format_duration(1, TimeUnit.MONTHS, "es") == "un mes"
    assert format_duration(2, TimeUnit.MONTHS, "en") == "2 months"
    assert format_duration(45, TimeUnit.CALENDAR_DAYS, "en") == "45 calendar days"


def datetime_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _pdf_text(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(data)).pages)


def test_pdf_is_deterministic_and_keeps_the_disclaimer() -> None:
    document = build_access_request(SYNTHETIC, EXAMPLE, packs_root=PACKS, today=TODAY)
    meta = PdfMetadata(
        title=document.title, language=document.language, created=datetime_utc(TODAY)
    )
    first = render_pdf(document.markdown, meta)
    assert first == render_pdf(document.markdown, meta)
    reader = pypdf.PdfReader(io.BytesIO(first))
    assert len(reader.pages) >= 2  # the note is on its own page
    text = _pdf_text(first).lower()
    assert "not legal advice" in text
    assert "alex example" in text


def test_pdf_writes_undrawable_characters_as_code_points() -> None:
    assert drawable("Ñandú, Ελλάδα, Москва\n") == "Ñandú, Ελλάδα, Москва\n"
    assert drawable("I \u2764\ufe0f it") == "I [U+2764][U+FE0F] it"
    data = render_pdf(
        "x \U0001f3f4", PdfMetadata(title="t", language="en", created=datetime_utc(TODAY))
    )
    assert "[U+1F3F4]" in _pdf_text(data)


def test_pdf_renders_every_supported_block(tmp_path: Path) -> None:
    markdown = (
        "# H1\n## H2\n### H3\n\nLine one\\\nline two **bold**\n\n- bullet\n  continued\n"
        "   - sub-item\n     wrapped\n"
        "1. first\n\n> quote\n> more\n>\n> - item\n>   - nested\n\n---\n\n<!-- pagebreak -->\n\nend"
    )
    data = render_pdf(markdown, PdfMetadata(title="t", language="en", created=datetime_utc(TODAY)))
    text = _pdf_text(data)
    for expected in (
        "H1",
        "H3",
        "line two bold",
        "bullet continued",
        "sub-item wrapped",
        "first",
        "quote more",
        "nested",
        "end",
    ):
        assert expected in text
