"""Draft a request for access to detector reports and related personal data.

The letter body comes from the jurisdiction pack's template. The note for the student and
the footer are added here, in code, so that no template can drop the "not legal advice"
statement. Nothing is sent anywhere: the student reviews and sends the letter themselves.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from draftwitness import __version__
from draftwitness.core.facts import Fact, Verification
from draftwitness.core.jurisdictions import (
    ResolvedAccessRequest,
    load_pack,
    resolve_access_request,
)
from draftwitness.core.jurisdictions.models import ResponseDeadline, localized
from draftwitness.core.profiles import Profile, resolve
from draftwitness.core.profiles.models import (
    Contact,
    ContactRole,
    Institution,
    Policies,
    Slug,
    TimeUnit,
)
from draftwitness.core.render.pdf import PAGE_BREAK
from draftwitness.i18n import t, tr

#: Display names for tool identifiers used in profiles and reports.
TOOL_NAMES: Final = {
    "turnitin": "Turnitin",
    "safeassign": "SafeAssign",
    "strikeplagiarism": "StrikePlagiarism",
    "compilatio": "Compilatio",
    "copyleaks": "Copyleaks",
    "gptzero": "GPTZero",
    "originality-ai": "Originality.ai",
    "pangram": "Pangram",
    "ouriginal": "Ouriginal",
    "ithenticate": "iThenticate",
}


UNLISTED_ID: Final = "other"
"""Institution id of the profile built for an institution DraftWitness has no profile for."""

_PACK_COUNTRIES: Final = {"uk": "GB"}
"""Country code of packs whose id is not one."""


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class StudentDetails(_Input):
    """Who is asking. Used only to fill in the letter; never stored or sent."""

    name: str = Field(min_length=1)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    student_id: str | None = None
    identity_document: str | None = Field(
        default=None, description="National ID or passport number, if the university asks for it."
    )
    postal_address: str | None = None
    programme: str | None = None


class RequestDetails(_Input):
    """Which work and which checks the request is about."""

    submission_title: str | None = None
    submission_date: date | None = None
    course: str | None = None
    tools: list[Slug] = Field(
        default=[], description="Tool ids; defaults to the tools listed in the profile."
    )
    extra_items: list[str] = Field(default=[], description="Additional items to request.")


class AccessRequestInput(_Input):
    """The student file accepted by ``draftwitness access-request --student``."""

    student: StudentDetails
    request: RequestDetails = RequestDetails()


class AccessRequestError(ValueError):
    """The request cannot be drafted with the given profile, pack or language."""


@dataclass(frozen=True)
class AccessRequestDocument:
    markdown: str
    title: str
    language: str
    jurisdiction: str
    profile_id: str
    recipient: Contact | None
    unverified: tuple[str, ...]
    """Citations or labels (in the interface language) of facts used in the document that
    still need verification."""


def unlisted_profile(
    packs_root: Path,
    pack_id: str,
    institution: str,
    *,
    office: str | None = None,
    office_email: str | None = None,
) -> Profile:
    """A minimal profile for an institution with no bundled profile: the letter then relies on
    the jurisdiction pack alone. ``office`` and ``office_email`` are the recipient the student
    found; they are used as given and flagged as unverified."""
    resolved = resolve_access_request(packs_root, pack_id)
    own = load_pack(packs_root, pack_id).access_request
    languages = list(dict.fromkeys([*(own.templates if own else {}), *resolved.template_files]))
    office, office_email = (office or "").strip(), (office_email or "").strip()
    if bool(office) != bool(office_email):
        raise AccessRequestError(t("access.office_and_email"))
    contacts: list[Fact[Contact]] = []
    if office_email:
        role = next(iter(resolved.spec.recipient_roles), ContactRole.OTHER)
        try:
            contact = Contact(role=role, name=office, email=office_email)
        except ValidationError as exc:
            raise AccessRequestError(t("access.office_email_invalid", email=office_email)) from exc
        contacts.append(Fact[Contact](value=contact))
    country = _PACK_COUNTRIES.get(pack_id, pack_id.upper())
    try:
        return Profile(
            id=f"{country.lower()}/{UNLISTED_ID}",
            country=country,
            jurisdictions=list(reversed(resolved.chain)),
            languages=languages,
            institution=Institution(
                id=UNLISTED_ID, name=institution, policies=Policies(contacts=contacts)
            ),
        )
    except ValidationError as exc:
        raise AccessRequestError(t("access.institution_missing")) from exc


def add_business_days(start: date, days: int) -> date:
    """``start`` plus ``days`` weekdays. Public holidays are not known, so not skipped."""
    current = start
    remaining = days
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def due_date(start: date, amount: int, unit: TimeUnit) -> date:
    if unit is TimeUnit.MONTHS:
        return add_months(start, amount)
    if unit is TimeUnit.BUSINESS_DAYS:
        return add_business_days(start, amount)
    return start + timedelta(days=amount)


def format_date(value: date, language: str) -> str:
    months = tr(language, "dates.months").split(",")
    return tr(language, "dates.long", day=value.day, month=months[value.month - 1], year=value.year)


def format_duration(amount: int, unit: TimeUnit, language: str) -> str:
    if unit is TimeUnit.MONTHS:
        if amount == 1:
            return tr(language, "durations.months_one")
        return tr(language, "durations.months_many", n=amount)
    return tr(language, f"durations.{unit.value}", n=amount)


def _choose_language(
    profile: Profile, resolved: ResolvedAccessRequest, requested: str | None
) -> str:
    available = list(resolved.template_files)
    if requested is not None:
        if requested not in available:
            raise AccessRequestError(
                f"no {requested!r} template in pack {resolved.chain[0]!r}; "
                f"available: {', '.join(available)}"
            )
        return requested
    for language in profile.languages:
        if language in available:
            return language
    return available[0]


def _choose_recipient(
    contacts: list[Fact[Contact]], resolved: ResolvedAccessRequest
) -> Fact[Contact] | None:
    for role in resolved.spec.recipient_roles:
        for contact in contacts:
            if contact.value.role is role:
                return contact
    return None


def _recipient_block(contact: Contact, institution: str) -> str:
    """Address lines for the letter head, joined with Markdown hard line breaks."""
    lines = [f"{contact.name}, {institution}", contact.postal_address, contact.email]
    return "\\\n".join(line for line in lines if line)


def _recipient_line(contact: Contact) -> str:
    channels = [c for c in (contact.email, contact.postal_address, contact.url) if c]
    return f"{contact.name} ({'; '.join(channels)})"


def _student_note(
    *,
    language: str,
    resolved: ResolvedAccessRequest,
    recipient: Fact[Contact] | None,
    sent_on: date,
    unverified: list[str],
) -> str:
    spec = resolved.spec
    lines = [f"> **{tr(language, 'documents.note_title')}**", ">"]

    def item(text: str) -> None:
        lines.append(f"> - {text}")

    lines.append(f"> {tr(language, 'documents.note_not_legal_advice')}")
    lines.append(">")
    if recipient is not None:
        item(tr(language, "documents.note_send_to", recipient=_recipient_line(recipient.value)))
    else:
        item(tr(language, "documents.note_send_to_unknown"))
    item(tr(language, "documents.note_proof"))
    if spec.response_deadline is not None:
        deadline: ResponseDeadline = spec.response_deadline.value
        item(
            tr(
                language,
                "documents.note_deadline",
                duration=format_duration(deadline.amount, deadline.unit, language),
                from_event=localized(deadline.from_event, language),
                sent=format_date(sent_on, language),
                due=format_date(due_date(sent_on, deadline.amount, deadline.unit), language),
            )
        )
        if deadline.extension_amount and deadline.extension_unit:
            item(
                tr(
                    language,
                    "documents.note_extension",
                    duration=format_duration(
                        deadline.extension_amount, deadline.extension_unit, language
                    ),
                    condition=localized(deadline.extension_condition or "", language),
                )
            )
    if spec.authority is not None:
        authority = spec.authority.value
        item(
            tr(
                language,
                "documents.note_authority",
                name=localized(authority.name, language),
                url=authority.url,
            )
        )
    for prerequisite in spec.prerequisites:
        item(
            tr(
                language,
                "documents.note_prerequisite",
                text=localized(prerequisite.value, language),
            )
        )
    item(tr(language, "documents.note_bases"))
    for basis in spec.legal_bases:
        flag = (
            tr(language, "documents.note_flag_unverified")
            if basis.verification is Verification.NEEDS_VERIFICATION
            else ""
        )
        lines.append(
            "> "
            + "  - "
            + tr(
                language,
                "documents.note_basis",
                citation=basis.value.citation,
                summary=localized(basis.value.summary, language),
                flag=flag,
            )
        )
    if unverified:
        lines.append(">")
        lines.append(f"> {tr(language, 'documents.note_unverified', count=len(unverified))}")
    return "\n".join(lines)


def _environment(template_dir: Path) -> SandboxedEnvironment:
    return SandboxedEnvironment(
        loader=FileSystemLoader(template_dir),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def build_access_request(
    profile: Profile,
    data: AccessRequestInput,
    *,
    packs_root: Path,
    today: date,
    path: str | None = None,
    jurisdiction: str | None = None,
    language: str | None = None,
) -> AccessRequestDocument:
    """Draft the request. Pure function: reads templates, writes nothing."""
    pack_id = jurisdiction or profile.jurisdictions[-1]
    resolved = resolve_access_request(packs_root, pack_id)
    language = _choose_language(profile, resolved, language)
    policies = resolve(profile, path).policies
    recipient = _choose_recipient(policies.contacts, resolved)

    tools = list(data.request.tools) or [t.value.tool for t in policies.tools if t.value.enabled]
    tool_names = list(dict.fromkeys(TOOL_NAMES.get(t, t) for t in tools))

    facts: list[tuple[str, Fact[Any]]] = [(b.value.citation, b) for b in resolved.spec.legal_bases]
    if resolved.spec.response_deadline is not None:
        facts.append((t("access.label_deadline"), resolved.spec.response_deadline))
    if resolved.spec.authority is not None:
        facts.append((t("access.label_authority"), resolved.spec.authority))
    if recipient is not None:
        facts.append((t("access.label_recipient"), recipient))
    unverified = [
        label for label, fact in facts if fact.verification is Verification.NEEDS_VERIFICATION
    ]

    template_file = resolved.template_files[language]
    context: dict[str, Any] = {
        "student": data.student,
        "request": data.request,
        "tools": tool_names,
        "institution": profile.institution.name,
        "recipient": recipient.value if recipient else None,
        "recipient_block": _recipient_block(recipient.value, profile.institution.name)
        if recipient
        else None,
        "date": format_date(today, language),
        "submission_date": (
            format_date(data.request.submission_date, language)
            if data.request.submission_date
            else None
        ),
        "deadline": resolved.spec.response_deadline.value
        if resolved.spec.response_deadline
        else None,
        "duration": lambda d: format_duration(d.amount, d.unit, language),
        "localized": lambda text: localized(text, language),
    }
    body = _environment(template_file.parent).get_template(template_file.name).render(context)
    title = next(
        (line.lstrip("# ").strip() for line in body.splitlines() if line.startswith("# ")),
        "Access request",
    )
    note = _student_note(
        language=language,
        resolved=resolved,
        recipient=recipient,
        sent_on=today,
        unverified=unverified,
    )
    footer = tr(language, "documents.footer", version=__version__)
    markdown = f"{note}\n\n{PAGE_BREAK}\n\n{body.strip()}\n\n---\n\n{footer}\n"
    return AccessRequestDocument(
        markdown=markdown,
        title=title,
        language=language,
        jurisdiction=pack_id,
        profile_id=profile.id,
        recipient=recipient.value if recipient else None,
        unverified=tuple(unverified),
    )


NOT_LEGAL_ADVICE_MARKERS: Final = {
    "en": "not legal advice",
    "es": "no es asesoramiento legal",
}
"""Phrases that every generated document must contain, per language (checked in tests)."""
