"""pydantic models for institution profiles, schema v0.1.

A profile describes one institution as a tree: institution → faculty → degree → course.
Every node may carry ``policies``; a child's policies refine its parent's (see
:mod:`draftwitness.core.profiles.resolve`).

Names, identifiers and official URLs identify a node. Everything that can change over time
(AI policy, thresholds, tools, regulations, deadlines, contacts) is a :class:`Fact`, which
carries its source URL, effective date and verification status.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROFILE_SCHEMA_VERSION: Final = "0.1"

Percent = Annotated[float, Field(ge=0, le=100)]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=64)]
Url = Annotated[str, Field(pattern=r"^https?://\S+$", max_length=2048)]
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
LanguageCode = Annotated[str, Field(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Verification(StrEnum):
    """Whether a human has checked a fact against an official source."""

    VERIFIED = "verified"
    NEEDS_VERIFICATION = "needs_verification"


def _fact_schema_extra(schema: dict[str, Any]) -> None:
    schema["if"] = {
        "required": ["verification"],
        "properties": {"verification": {"const": Verification.VERIFIED.value}},
    }
    schema["then"] = {
        "required": ["source_url", "checked_on"],
        "properties": {"source_url": {"type": "string"}, "checked_on": {"type": "string"}},
    }


class Fact[T](_Model):
    """A value plus where it comes from.

    ``verified`` means someone checked ``value`` against the official page at
    ``source_url`` on ``checked_on``. Anything else is ``needs_verification``.
    """

    model_config = ConfigDict(json_schema_extra=_fact_schema_extra)

    value: T
    source_url: Url | None = None
    effective_date: date | None = Field(
        default=None, description="Date from which the rule applies, if the source states one."
    )
    checked_on: date | None = Field(
        default=None, description="Date someone last checked the value against the source."
    )
    verification: Verification = Verification.NEEDS_VERIFICATION
    quote: str | None = Field(
        default=None,
        max_length=400,
        description="Short verbatim excerpt from the source that supports the value.",
    )
    note: str | None = None

    @model_validator(mode="after")
    def _verified_needs_evidence(self) -> Self:
        if self.verification is Verification.VERIFIED and (
            self.source_url is None or self.checked_on is None
        ):
            raise ValueError("a verified fact needs source_url and checked_on")
        return self


class AiStance(StrEnum):
    """Institution's stance on students using generative AI."""

    PROHIBITED = "prohibited"
    ALLOWED_WITH_DISCLOSURE = "allowed_with_disclosure"
    INSTRUCTOR_DECIDES = "instructor_decides"
    ALLOWED = "allowed"
    UNSPECIFIED = "unspecified"


class AiPolicy(_Model):
    stance: AiStance
    summary: str = Field(min_length=1)
    disclosure_required: bool | None = None


class ThresholdKind(StrEnum):
    """How a similarity threshold is used."""

    HARD = "hard"
    """Exceeding it has an automatic consequence (e.g. the work is not accepted)."""
    INDICATIVE = "indicative"
    """Exceeding it triggers a human review."""
    NONE_PUBLISHED = "none_published"
    """The institution states, or its rules imply, that there is no numeric threshold."""


class SimilarityThreshold(_Model):
    kind: ThresholdKind
    percent: Percent | None = None
    applies_to: str | None = Field(
        default=None, description="Kind of work, e.g. 'bachelor thesis', 'doctoral thesis'."
    )

    @model_validator(mode="after")
    def _percent_matches_kind(self) -> Self:
        if self.kind is ThresholdKind.NONE_PUBLISHED and self.percent is not None:
            raise ValueError("none_published thresholds have no percent")
        if self.kind is not ThresholdKind.NONE_PUBLISHED and self.percent is None:
            raise ValueError(f"{self.kind.value} thresholds need a percent")
        return self


class ToolFeature(StrEnum):
    SIMILARITY = "similarity"
    AI_WRITING = "ai_writing"


class ToolUse(_Model):
    tool: Slug = Field(description="Same identifiers as the report schema, e.g. 'turnitin'.")
    features: list[ToolFeature] = Field(min_length=1)
    enabled: bool = Field(
        default=True, description="False records a feature the institution has switched off."
    )


class RegulationTopic(StrEnum):
    ACADEMIC_INTEGRITY = "academic_integrity"
    DISCIPLINE = "discipline"
    ASSESSMENT = "assessment"
    APPEALS = "appeals"
    THESES = "theses"
    DATA_PROTECTION = "data_protection"
    RECORDS_ACCESS = "records_access"
    AI_USE = "ai_use"


class Regulation(_Model):
    title: str = Field(min_length=1)
    topics: list[RegulationTopic] = Field(min_length=1)
    articles: list[str] = Field(
        default=[], description="Relevant articles or sections, e.g. 'art. 7'."
    )


class DeadlineKind(StrEnum):
    GRADE_REVIEW = "grade_review"
    GRADE_APPEAL = "grade_appeal"
    MISCONDUCT_APPEAL = "misconduct_appeal"
    RECORDS_ACCESS_RESPONSE = "records_access_response"
    OTHER = "other"


class TimeUnit(StrEnum):
    CALENDAR_DAYS = "calendar_days"
    BUSINESS_DAYS = "business_days"
    MONTHS = "months"


class Deadline(_Model):
    kind: DeadlineKind
    amount: Annotated[int, Field(ge=1)]
    unit: TimeUnit
    from_event: str = Field(
        min_length=1, description="What starts the clock, e.g. 'publication of grades'."
    )


class ContactRole(StrEnum):
    DATA_PROTECTION_OFFICER = "data_protection_officer"
    RECORDS_OFFICE = "records_office"
    OMBUDS = "ombuds"
    ACADEMIC_INTEGRITY_OFFICE = "academic_integrity_office"
    OTHER = "other"


class Contact(_Model):
    role: ContactRole
    name: str = Field(min_length=1)
    email: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")] | None = None
    url: Url | None = None
    postal_address: str | None = None

    @model_validator(mode="after")
    def _has_a_channel(self) -> Self:
        if self.email is None and self.url is None and self.postal_address is None:
            raise ValueError("a contact needs an email, url or postal_address")
        return self


class Policies(_Model):
    """Policies stated at one level of the tree. All fields are optional."""

    ai_policy: Fact[AiPolicy] | None = None
    similarity_thresholds: list[Fact[SimilarityThreshold]] = []
    tools: list[Fact[ToolUse]] = []
    regulations: list[Fact[Regulation]] = []
    deadlines: list[Fact[Deadline]] = []
    self_plagiarism: Fact[str] | None = Field(
        default=None, description="Rule on reusing one's own earlier work, summarised."
    )
    contacts: list[Fact[Contact]] = []


class Node(_Model):
    """Common fields of every level of the tree."""

    id: Slug
    name: str = Field(min_length=1)
    official_url: Url | None = None
    policies: Policies = Policies()


def _unique_ids(nodes: list[Any], what: str) -> None:
    ids = [n.id for n in nodes]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate {what} ids: {', '.join(duplicates)}")


class Course(Node):
    pass


class DegreeLevel(StrEnum):
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"
    OTHER = "other"


class Degree(Node):
    level: DegreeLevel
    courses: list[Course] = []

    @model_validator(mode="after")
    def _children_unique(self) -> Self:
        _unique_ids(self.courses, "course")
        return self


class Faculty(Node):
    degrees: list[Degree] = []

    @model_validator(mode="after")
    def _children_unique(self) -> Self:
        _unique_ids(self.degrees, "degree")
        return self


class Institution(Node):
    faculties: list[Faculty] = []

    @model_validator(mode="after")
    def _children_unique(self) -> Self:
        _unique_ids(self.faculties, "faculty")
        return self


def _profile_schema_extra(schema: dict[str, Any]) -> None:
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:draftwitness:schema:profile:{PROFILE_SCHEMA_VERSION}"
    schema["required"] = ["schema_version", *schema.get("required", [])]


class Profile(_Model):
    """An institution profile. One YAML file per institution."""

    model_config = ConfigDict(
        title="DraftWitness institution profile", json_schema_extra=_profile_schema_extra
    )

    schema_version: Literal["0.1"] = PROFILE_SCHEMA_VERSION
    id: Annotated[str, Field(pattern=r"^[a-z]{2}/[a-z0-9][a-z0-9-]*$")] = Field(
        description="'<country>/<institution>', e.g. 'es/uah'. Matches the file path."
    )
    country: CountryCode
    jurisdictions: list[Slug] = Field(
        min_length=1, description="Jurisdiction packs that apply, most general first."
    )
    languages: list[LanguageCode] = Field(
        min_length=1, description="Languages the institution accepts documents in."
    )
    institution: Institution

    @model_validator(mode="after")
    def _id_matches(self) -> Self:
        country, slug = self.id.split("/")
        if country != self.country.lower():
            raise ValueError(f"profile id {self.id!r} does not start with country {self.country}")
        if slug != self.institution.id:
            raise ValueError(f"profile id {self.id!r} does not end with {self.institution.id!r}")
        return self
