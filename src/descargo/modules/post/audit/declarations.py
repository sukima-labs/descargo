"""The student's declarations file: own earlier work and institution template text.

These are the student's own statements. The auditor applies them but labels every
discount based on them as declared by the student, so a reader can weigh them.
"""

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from descargo.core.documents import DocumentError, extract_text


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class OwnWork(_Input):
    """A report source that is the student's own earlier work."""

    source: str = Field(
        min_length=1, description="Source id (e.g. 's2') or its label as shown on the report."
    )
    description: str = Field(
        min_length=1,
        description="What the earlier work is and, if it applies, who authorised reusing it.",
    )


class Template(_Input):
    """Text supplied by the institution: an assignment brief, a cover page, a form."""

    description: str = Field(min_length=1)
    text: str | None = None
    file: str | None = Field(
        default=None,
        description="Path to a .txt, .md, .docx, .odt or .pdf file, relative "
        "to the declarations file.",
    )
    source: str | None = Field(
        default=None, description="A report source that is the template itself (id or label)."
    )

    @model_validator(mode="after")
    def _one_kind(self) -> Self:
        given = [x for x in (self.text, self.file, self.source) if x]
        if len(given) != 1:
            raise ValueError("a template needs exactly one of text, file or source")
        return self


class Declarations(_Input):
    own_work: list[OwnWork] = []
    templates: list[Template] = []


class DeclarationsError(ValueError):
    """The declarations file cannot be read."""


def load_declarations(path: Path) -> Declarations:
    """Read the declarations file; template files are read into ``text``."""
    try:
        data = yaml.safe_load(path.read_text("utf-8")) or {}
        declarations = Declarations.model_validate(data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise DeclarationsError(f"{path}: {exc}") from exc
    templates: list[Template] = []
    for template in declarations.templates:
        if template.file:
            try:
                text = extract_text(path.parent / template.file).text
            except (OSError, DocumentError) as exc:
                raise DeclarationsError(f"{path}: template {template.file!r}: {exc}") from exc
            templates.append(template.model_copy(update={"text": text}))
        else:
            templates.append(template)
    return declarations.model_copy(update={"templates": templates})
