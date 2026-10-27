"""Sourced facts: a value plus where it comes from and whether a human checked it.

Used by institution profiles and jurisdiction packs alike.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Url = Annotated[str, Field(pattern=r"^https?://\S+$", max_length=2048)]


class Verification(StrEnum):
    """Whether someone has checked a fact against an official source."""

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


class Fact[T](BaseModel):
    """A value plus where it comes from.

    ``verified`` means someone checked ``value`` against the official page at
    ``source_url`` on ``checked_on``. Anything else is ``needs_verification``.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra=_fact_schema_extra,
    )

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
