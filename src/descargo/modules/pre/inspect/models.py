"""What the inspector reports (ADR 006): facts about a file, grouped by level, never a score."""

from datetime import date
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict

from descargo import __version__

INSPECTION_FORMAT_VERSION: Final = "0.1"
MAX_OCCURRENCES: Final = 10
"""Occurrences listed per finding; ``count`` always has the total."""
MAX_SAMPLE: Final = 200
"""Characters kept from a hidden passage or decoded message."""


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Level(StrEnum):
    REVIEW = "review"
    """A reader or a tool is likely to notice this. Not "this is wrong"."""
    INFO = "info"
    """Common and usually innocent."""


class FindingKind(StrEnum):
    # Characters
    FORMAT_CHARACTERS = "format_characters"
    JOINERS = "joiners"
    SOFT_HYPHENS = "soft_hyphens"
    BIDI_CONTROLS = "bidi_controls"
    BIDI_OVERRIDES = "bidi_overrides"
    BIDI_UNBALANCED = "bidi_unbalanced"
    TAG_CHARACTERS = "tag_characters"
    EMOJI_TAG_FLAGS = "emoji_tag_flags"
    VARIATION_SELECTORS = "variation_selectors"
    HIDDEN_DATA = "hidden_data"
    C2PA_MANIFEST = "c2pa_manifest"
    CONTROL_CHARACTERS = "control_characters"
    PRIVATE_USE = "private_use"
    UNASSIGNED = "unassigned"
    UNUSUAL_SPACES = "unusual_spaces"
    NO_BREAK_SPACES = "no_break_spaces"
    BLANK_FILLERS = "blank_fillers"
    LINE_SEPARATORS = "line_separators"
    MIXED_SCRIPT_WORDS = "mixed_script_words"
    BYTE_ORDER_MARK = "byte_order_mark"
    # Word processing documents
    RSIDS = "rsids"
    EDITING_TIME = "editing_time"
    EDITING_CYCLES = "editing_cycles"
    TRACKED_CHANGES = "tracked_changes"
    COMMENTS = "comments"
    HIDDEN_TEXT = "hidden_text"
    WHITE_TEXT = "white_text"
    TINY_TEXT = "tiny_text"
    FIELDS = "fields"
    ALT_CHUNKS = "alt_chunks"
    EMBEDDED_OBJECTS = "embedded_objects"
    MACROS = "macros"
    ATTACHED_TEMPLATE = "attached_template"
    # PDF
    INCREMENTAL_UPDATES = "incremental_updates"
    ENCRYPTED = "encrypted"
    ATTACHMENTS = "attachments"
    INVISIBLE_TEXT = "invisible_text"


class Location(_Out):
    """Where something was found. ``part`` is an archive member (DOCX, ODT) or omitted."""

    part: str | None = None
    paragraph: int | None = None
    page: int | None = None
    line: int | None = None


class Occurrence(_Out):
    location: Location
    text: str | None = None
    """The passage concerned, with invisible characters written as ``[U+XXXX]``."""


class CodePoint(_Out):
    code: str
    """``U+200B``."""
    name: str
    count: int


class Finding(_Out):
    kind: FindingKind
    level: Level
    count: int
    code_points: list[CodePoint] = []
    occurrences: list[Occurrence] = []
    """At most :data:`MAX_OCCURRENCES`."""
    details: dict[str, str | int] = {}
    """Kind-specific facts, for example the decoded text of tag characters."""


class MetadataField(_Out):
    part: str
    """``docProps/core.xml``, ``meta.xml``, ``Info``, ``XMP``…"""
    name: str
    value: str


class InspectedFile(_Out):
    filename: str
    sha256: str
    size_bytes: int
    format: str
    """``text``, ``docx``, ``odt`` or ``pdf``."""


class Inspection(_Out):
    inspection_format: str = INSPECTION_FORMAT_VERSION
    draftwitness_version: str = __version__
    generated_on: date
    unidata_version: str
    """Unicode version of the character database used; categories depend on it."""
    file: InspectedFile
    findings: list[Finding]
    metadata: list[MetadataField]
    notes: list[str] = []
    """Codes of ``inspect.note_<code>`` messages: parts that could not be read, limits."""

    def by_level(self, level: Level) -> list[Finding]:
        return [finding for finding in self.findings if finding.level is level]
