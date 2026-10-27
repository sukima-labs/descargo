"""pydantic models for report schema v0.1 (ADR 004).

These models are the single source of truth: the published JSON Schema in
``schemas/report/`` is generated from them, and a test fails if the two drift apart.

The schema records what a detector *said*. It never records the student's interpretation,
and it deliberately has no field for the student's name, email, student number or the
instructor's name (data minimisation).
"""

from enum import StrEnum
from typing import Annotated, Any, Final, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

SCHEMA_VERSION: Final = "0.1"

Percent = Annotated[float, Field(ge=0, le=100)]
NonNegativeInt = Annotated[int, Field(ge=0)]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$", max_length=64)]
LocalId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$", max_length=64)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ReportKind(StrEnum):
    """What the downloaded report covers."""

    SIMILARITY = "similarity"
    AI_WRITING = "ai_writing"
    COMBINED = "combined"


class SourceKind(StrEnum):
    """Category of a matched source, as the tool reports it."""

    INTERNET = "internet"
    PUBLICATION = "publication"
    STUDENT_PAPER = "student_paper"
    OTHER = "other"
    UNKNOWN = "unknown"


class Tool(_Model):
    """The detector that produced the report."""

    name: Slug = Field(description="Tool identifier, e.g. 'turnitin', 'copyleaks', 'gptzero'.")
    product: str | None = Field(
        default=None, description="Product or integration name as shown on the report."
    )
    version: str | None = Field(
        default=None, description="Tool or report-format version, if the report shows one."
    )
    report_kind: ReportKind


class ReportFile(_Model):
    """The file the student downloaded and fed to the adapter."""

    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(examples=["application/pdf", "text/html"])
    sha256: Sha256
    size_bytes: NonNegativeInt


class Provenance(_Model):
    """How this report object was produced, so a third party can reproduce it."""

    adapter: Slug = Field(description="Adapter that parsed the report, e.g. 'turnitin-pdf'.")
    adapter_version: str = Field(min_length=1)
    draftwitness_version: str = Field(min_length=1)
    parsed_at: AwareDatetime
    report_file: ReportFile | None = Field(
        default=None, description="Absent when the report was entered by hand."
    )


class Submission(_Model):
    """The submitted work, as described by the report. No personal data."""

    title: str | None = None
    submission_id: str | None = Field(
        default=None, description="Tool-assigned submission identifier (not a student ID)."
    )
    submitted_at: AwareDatetime | None = None
    word_count: NonNegativeInt | None = None
    character_count: NonNegativeInt | None = None
    page_count: NonNegativeInt | None = None


class SimilarityFilters(_Model):
    """Exclusions the report says were applied. ``None`` means the report does not say."""

    quotes_excluded: bool | None = None
    bibliography_excluded: bool | None = None
    small_matches_excluded: bool | None = None
    small_matches_min_words: NonNegativeInt | None = None
    small_matches_min_percent: Percent | None = None


class Source(_Model):
    """One matched source in the report's source list."""

    id: LocalId = Field(description="Identifier unique within this report, e.g. 's1'.")
    rank: Annotated[int, Field(ge=1)] | None = Field(
        default=None, description="Position in the tool's source list."
    )
    label: str = Field(min_length=1, description="Source name or URL as shown on the report.")
    kind: SourceKind = SourceKind.UNKNOWN
    url: str | None = None
    percent: Percent | None = Field(
        default=None, description="Share of the submission attributed to this source."
    )
    percent_is_upper_bound: bool = Field(
        default=False,
        description="True when the report shows a bound such as '<1%'; percent is then the bound.",
    )
    matched_words: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _bound_needs_percent(self) -> Self:
        if self.percent_is_upper_bound and self.percent is None:
            raise ValueError("percent_is_upper_bound requires percent")
        return self


class Match(_Model):
    """One matched passage. Most downloaded reports expose only some of these fields."""

    id: LocalId
    source_id: LocalId
    text: str | None = Field(default=None, description="Matched text in the submission.")
    start: NonNegativeInt | None = Field(
        default=None, description="Start offset in the submission's extracted text."
    )
    end: NonNegativeInt | None = Field(
        default=None, description="End offset (exclusive) in the submission's extracted text."
    )
    page: Annotated[int, Field(ge=1)] | None = None
    word_count: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _offsets_are_consistent(self) -> Self:
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be given together")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class Similarity(_Model):
    """Similarity section of a report."""

    overall_percent: Percent
    filters: SimilarityFilters = SimilarityFilters()
    sources: list[Source] = []
    matches: list[Match] = []

    @model_validator(mode="after")
    def _references_are_consistent(self) -> Self:
        source_ids = [s.id for s in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source ids must be unique")
        match_ids = [m.id for m in self.matches]
        if len(match_ids) != len(set(match_ids)):
            raise ValueError("match ids must be unique")
        known = set(source_ids)
        unknown = sorted({m.source_id for m in self.matches} - known)
        if unknown:
            raise ValueError(f"matches refer to unknown sources: {', '.join(unknown)}")
        return self


class AiSegment(_Model):
    """A stretch of text the AI-writing detector flagged."""

    text: str | None = None
    start: NonNegativeInt | None = None
    end: NonNegativeInt | None = None
    page: Annotated[int, Field(ge=1)] | None = None
    score: Percent | None = Field(
        default=None, description="Tool-reported score for this segment, scaled to 0-100."
    )
    label: str | None = None

    @model_validator(mode="after")
    def _offsets_are_consistent(self) -> Self:
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be given together")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class AiWriting(_Model):
    """AI-writing section of a report."""

    overall_percent: Percent | None = Field(
        default=None, description="Share of text the tool attributes to AI, 0-100."
    )
    label: str | None = Field(
        default=None, description="Verdict label as shown, e.g. 'Likely AI-generated'."
    )
    detector_model: str | None = Field(
        default=None, description="Detector model or version, if the report names one."
    )
    segments: list[AiSegment] = []

    @model_validator(mode="after")
    def _has_a_result(self) -> Self:
        if self.overall_percent is None and self.label is None:
            raise ValueError("ai_writing needs overall_percent or label")
        return self


def _report_schema_extra(schema: dict[str, Any]) -> None:
    """Publish what pydantic enforces but cannot express on its own.

    ``schema_version`` has a default in Python but is required in files, and the rule tying
    ``tool.report_kind`` to the sections present is spelled out with ``if``/``then``. The
    rule that every match refers to a listed source is enforced by this implementation only.
    """
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:draftwitness:schema:report:{SCHEMA_VERSION}"
    schema["required"] = ["schema_version", *schema.get("required", [])]

    def kind_is(kind: ReportKind) -> dict[str, Any]:
        return {"properties": {"tool": {"properties": {"report_kind": {"const": kind.value}}}}}

    def section(name: str) -> dict[str, Any]:
        return {"required": [name], "properties": {name: {"type": "object"}}}

    schema["allOf"] = [
        {"if": kind_is(ReportKind.SIMILARITY), "then": section("similarity")},
        {"if": kind_is(ReportKind.AI_WRITING), "then": section("ai_writing")},
        {
            "if": kind_is(ReportKind.COMBINED),
            "then": {"anyOf": [section("similarity"), section("ai_writing")]},
        },
    ]


class Report(_Model):
    """A detector report in DraftWitness's common format."""

    model_config = ConfigDict(title="DraftWitness report", json_schema_extra=_report_schema_extra)

    schema_version: Literal["0.1"] = SCHEMA_VERSION
    tool: Tool
    provenance: Provenance
    submission: Submission = Submission()
    similarity: Similarity | None = None
    ai_writing: AiWriting | None = None
    warnings: list[str] = Field(
        default=[], description="What the adapter could not extract or had to interpret."
    )
    extensions: dict[Slug, dict[str, JsonValue]] = Field(
        default={},
        description="Tool-specific fields, namespaced by tool name.",
        json_schema_extra={"additionalProperties": False},
    )

    @model_validator(mode="after")
    def _sections_match_kind(self) -> Self:
        kind = self.tool.report_kind
        if kind is ReportKind.SIMILARITY and self.similarity is None:
            raise ValueError("a similarity report needs a similarity section")
        if kind is ReportKind.AI_WRITING and self.ai_writing is None:
            raise ValueError("an ai_writing report needs an ai_writing section")
        if kind is ReportKind.COMBINED and self.similarity is None and self.ai_writing is None:
            raise ValueError("a combined report needs at least one section")
        return self
