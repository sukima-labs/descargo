"""pydantic models for jurisdiction packs, schema v0.1.

A pack holds the legal bases, deadlines, supervisory authority and document templates for
one country or region. A pack may ``extend`` a more general one (Spain extends the EU): legal
bases and prerequisites accumulate, everything else is overridden by the more specific pack.
"""

from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from descargo.core.facts import Fact, Url
from descargo.core.profiles.models import ContactRole, LanguageCode, Slug, TimeUnit

PACK_SCHEMA_VERSION: Final = "0.1"

TemplatePath = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+\.md\.j2$")]

Localized = Annotated[
    str | dict[LanguageCode, Annotated[str, Field(min_length=1)]],
    Field(description="Plain text, or text per language with English as the fallback."),
]


def localized(text: Localized, language: str) -> str:
    """Pick ``language`` from a localized text, falling back to English, then any."""
    if isinstance(text, str):
        return text
    return text.get(language) or text.get("en") or next(iter(text.values()))


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class LegalBasis(_Model):
    """One provision the document relies on."""

    citation: str = Field(min_length=1, examples=["GDPR, Art. 15(1)(h)"])
    summary: Localized = Field(description="Plain-language summary for the student.")


class ResponseDeadline(_Model):
    amount: Annotated[int, Field(ge=1)]
    unit: TimeUnit
    from_event: Localized
    extension_amount: Annotated[int, Field(ge=1)] | None = None
    extension_unit: TimeUnit | None = None
    extension_condition: Localized | None = None


class Authority(_Model):
    """Where the student can complain if the request is ignored or refused."""

    name: Localized
    url: Url


class AccessRequestSpec(_Model):
    """Everything needed to draft a request for access to a detector report."""

    legal_bases: list[Fact[LegalBasis]] = []
    response_deadline: Fact[ResponseDeadline] | None = None
    authority: Fact[Authority] | None = None
    prerequisites: list[Fact[Localized]] = Field(
        default=[], description="Steps required before complaining to the authority."
    )
    recipient_roles: list[ContactRole] = Field(
        default=[], description="Profile contact roles to address, in order of preference."
    )
    templates: dict[LanguageCode, TemplatePath] = Field(
        default={}, description="Template file per language, relative to the pack folder."
    )


def _pack_schema_extra(schema: dict[str, Any]) -> None:
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:draftwitness:schema:jurisdiction:{PACK_SCHEMA_VERSION}"
    schema["required"] = ["schema_version", *schema.get("required", [])]


class Pack(_Model):
    """A jurisdiction pack. One ``pack.yaml`` per folder under ``jurisdictions/``."""

    model_config = ConfigDict(
        title="Descargo jurisdiction pack", json_schema_extra=_pack_schema_extra
    )

    schema_version: Literal["0.1"] = PACK_SCHEMA_VERSION
    id: Slug
    name: str = Field(min_length=1)
    extends: Slug | None = None
    access_request: AccessRequestSpec | None = None
