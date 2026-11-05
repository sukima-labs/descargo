"""Pieces shared by the per-format readers."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Final
from xml.etree.ElementTree import Element

from descargo.modules.pre.inspect.chars import Segment, visible
from descargo.modules.pre.inspect.models import (
    MAX_OCCURRENCES,
    MAX_SAMPLE,
    Finding,
    FindingKind,
    Level,
    Location,
    MetadataField,
    Occurrence,
)

MAX_VALUE: Final = 300
"""Characters kept from a metadata value."""

PREFIXES: Final = {
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://purl.org/dc/terms/": "dcterms",
    "http://schemas.openxmlformats.org/package/2006/metadata/core-properties": "cp",
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties": "app",
    "urn:oasis:names:tc:opendocument:xmlns:meta:1.0": "meta",
    "http://ns.adobe.com/xap/1.0/": "xmp",
    "http://ns.adobe.com/xap/1.0/mm/": "xmpMM",
    "http://ns.adobe.com/pdf/1.3/": "pdf",
    "http://ns.adobe.com/pdfx/1.3/": "pdfx",
    "http://www.aiim.org/pdfa/ns/id/": "pdfaid",
    "http://www.w3.org/1999/xlink": "xlink",
}


def qualified(tag: str) -> str:
    """``{uri}local`` as ``prefix:local`` for known namespaces, else ``local``."""
    if tag.startswith("{"):
        uri, _, local = tag[1:].partition("}")
        prefix = PREFIXES.get(uri)
        return f"{prefix}:{local}" if prefix else local
    return tag


def clip(text: str, limit: int = MAX_SAMPLE) -> str:
    text = " ".join(visible(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def metadata_field(part: str, name: str, value: str) -> MetadataField:
    return MetadataField(part=part, name=name, value=clip(value, MAX_VALUE))


def leaf_fields(root: Element, part: str) -> list[MetadataField]:
    """One field per child element of ``root`` that has text and no children."""
    return [
        metadata_field(part, qualified(child.tag), child.text.strip())
        for child in root
        if len(child) == 0 and child.text and child.text.strip()
    ]


def joined(names: Counter[str]) -> str:
    return ", ".join(sorted(name for name in names if name))


@dataclass
class Passages:
    """Runs of text with a property (hidden, white, tiny), counted and sampled."""

    count: int = 0
    characters: int = 0
    occurrences: list[Occurrence] = field(default_factory=list)

    def add(self, location: Location, text: str) -> None:
        if not text.strip():
            return
        self.count += 1
        self.characters += len(text)
        if len(self.occurrences) < MAX_OCCURRENCES:
            self.occurrences.append(Occurrence(location=location, text=clip(text)))

    def finding(self, kind: FindingKind, level: Level) -> Finding | None:
        if not self.count:
            return None
        return Finding(
            kind=kind,
            level=level,
            count=self.count,
            occurrences=self.occurrences,
            details={"characters": self.characters},
        )


@dataclass
class FormatResult:
    segments: list[Segment] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    metadata: list[MetadataField] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, finding: Finding | None) -> None:
        if finding is not None:
            self.findings.append(finding)
