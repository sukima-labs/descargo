"""Inspect an ODT file: text parts, ``meta.xml``, tracked changes, annotations, hidden text."""

import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Final
from xml.etree.ElementTree import Element

from draftwitness.core.documents.archive import DocumentError, parse_xml, read_member
from draftwitness.modules.pre.inspect.chars import Segment
from draftwitness.modules.pre.inspect.common import (
    FormatResult,
    Passages,
    joined,
    leaf_fields,
    metadata_field,
)
from draftwitness.modules.pre.inspect.models import Finding, FindingKind, Level, Location

TEXT: Final = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
OFFICE: Final = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
STYLE: Final = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"
FO: Final = "{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}"
META: Final = "{urn:oasis:names:tc:opendocument:xmlns:meta:1.0}"
DC: Final = "{http://purl.org/dc/elements/1.1/}"
XLINK: Final = "{http://www.w3.org/1999/xlink}"
TEXT_PARTS: Final = ("content.xml", "styles.xml")
TINY_POINTS: Final = 2.0
_PARAGRAPHS: Final = frozenset({f"{TEXT}p", f"{TEXT}h"})
_SIZE = re.compile(r"^([\d.]+)pt$")
_DURATION = re.compile(
    r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>[\d.]+)S)?)?$"
)
_CHANGES: Final = {
    f"{TEXT}insertion": "insertions",
    f"{TEXT}deletion": "deletions",
    f"{TEXT}format-change": "formatting",
}


_INLINE: Final = frozenset({f"{TEXT}s", f"{TEXT}tab", f"{TEXT}line-break"})


def _inline(element: Element) -> str:
    if element.tag == f"{TEXT}tab":
        return "\t"
    if element.tag == f"{TEXT}line-break":
        return "\n"
    count = element.get(f"{TEXT}c", "1")
    return " " * (int(count) if count.isdigit() else 1)


def duration_minutes(value: str) -> int | None:
    """Whole minutes in an ISO 8601 duration such as ``PT1H2M3S``; ``None`` if unreadable."""
    match = _DURATION.match(value.strip())
    if not match or value.strip() in {"P", "PT"}:
        return None
    days, hours, minutes = (int(match.group(g) or 0) for g in "dhm")
    seconds = float(match.group("s") or 0)
    return days * 1440 + hours * 60 + minutes + int(seconds // 60)


@dataclass(frozen=True)
class _TextProps:
    hidden: bool | None = None
    white: bool | None = None
    tiny: bool | None = None
    background: bool | None = None

    def over(self, base: "_TextProps") -> "_TextProps":
        return _TextProps(
            *(
                mine if mine is not None else theirs
                for mine, theirs in zip(
                    (self.hidden, self.white, self.tiny, self.background),
                    (base.hidden, base.white, base.tiny, base.background),
                    strict=True,
                )
            )
        )


@dataclass
class _Styles:
    props: dict[str, _TextProps] = field(default_factory=dict)
    parents: dict[str, str] = field(default_factory=dict)

    def read(self, root: Element) -> None:
        for style in root.iter(f"{STYLE}style"):
            name = style.get(f"{STYLE}name", "")
            parent = style.get(f"{STYLE}parent-style-name")
            if parent:
                self.parents[name] = parent
            text = style.find(f"{STYLE}text-properties")
            if text is None:
                continue
            display = text.get(f"{TEXT}display")
            color = text.get(f"{FO}color")
            size = _SIZE.match(text.get(f"{FO}font-size", ""))
            background = text.get(f"{FO}background-color")
            self.props[name] = _TextProps(
                hidden=None if display is None else display == "none",
                white=None if color is None else color.lower() == "#ffffff",
                tiny=None if size is None else float(size.group(1)) < TINY_POINTS,
                background=None
                if background is None
                else background.lower() not in {"transparent", "#ffffff"},
            )

    def resolve(self, name: str | None) -> _TextProps:
        props = _TextProps()
        seen: set[str] = set()
        while name and name not in seen:
            seen.add(name)
            props = props.over(self.props.get(name, _TextProps()))
            name = self.parents.get(name)
        return props


@dataclass
class _PartScan:
    part: str
    styles: _Styles
    hidden: Passages
    white: Passages
    tiny: Passages
    segments: list[Segment] = field(default_factory=list)

    def scan(self, root: Element) -> None:
        self._walk(root, [], Location(part=self.part), _TextProps())

    def _paragraph(self, element: Element, base: _TextProps) -> None:
        location = Location(part=self.part, paragraph=len(self.segments) + 1)
        index = len(self.segments)
        self.segments.append(Segment(location, ""))
        parts: list[str] = []
        props = self.styles.resolve(element.get(f"{TEXT}style-name")).over(base)
        self._collect(element, parts, location, props, base)
        self.segments[index] = Segment(location, "".join(parts))

    def _walk(
        self, element: Element, parts: list[str], location: Location, base: _TextProps
    ) -> None:
        for child in element:
            if child.tag in _PARAGRAPHS:
                self._paragraph(child, base)
            else:
                self._walk(child, parts, location, base)

    def _collect(
        self,
        element: Element,
        parts: list[str],
        location: Location,
        props: _TextProps,
        parent: _TextProps,
    ) -> None:
        """Gather ``element``'s text. A passage is counted where a property starts, not again
        in each element that inherits it."""
        own: list[str] = [element.text or ""]
        for child in element:
            tag = child.tag
            if tag in _PARAGRAPHS:
                self._paragraph(child, _TextProps())
            elif tag in _INLINE:
                own.append(_inline(child))
            elif tag == f"{TEXT}hidden-text":
                hidden = child.get(f"{TEXT}string-value", "")
                own.append(hidden)
                self.hidden.add(location, hidden)
            elif len(child) == 0 and not child.text:
                pass
            elif tag in {f"{TEXT}note", f"{OFFICE}annotation", f"{TEXT}note-body"}:
                self._walk(child, own, location, _TextProps())
            else:
                inner: list[str] = []
                style = child.get(f"{TEXT}style-name")
                child_props = self.styles.resolve(style).over(props) if style else props
                self._collect(child, inner, location, child_props, props)
                own.extend(inner)
            own.append(child.tail or "")
        content = "".join(own)
        parts.append(content)
        if parent.hidden:
            return
        if props.hidden:
            self.hidden.add(location, content)
        elif props.white and not props.background and not parent.white:
            self.white.add(location, content)
        if props.tiny and not parent.tiny:
            self.tiny.add(location, content)


def _meta(archive: zipfile.ZipFile, result: FormatResult) -> None:
    data = read_member(archive, "meta.xml")
    if data is None:
        return
    meta = parse_xml(data, "meta.xml").find(f"{OFFICE}meta")
    if meta is None:
        return
    result.metadata += [
        item for item in leaf_fields(meta, "meta.xml") if item.name != "meta:user-defined"
    ]
    for child in meta:
        if child.tag == f"{META}user-defined":
            name = child.get(f"{META}name", "")
            result.metadata.append(metadata_field("meta.xml", name, child.text or ""))
        elif child.tag in {f"{META}document-statistic", f"{META}template"}:
            value = ", ".join(f"{key.split('}')[-1]}={v}" for key, v in child.attrib.items())
            name = "meta:" + child.tag.split("}")[-1]
            result.metadata.append(metadata_field("meta.xml", name, value))
    duration = meta.findtext(f"{META}editing-duration")
    minutes = duration_minutes(duration) if duration else None
    if minutes is not None and duration:
        result.add(
            Finding(
                kind=FindingKind.EDITING_TIME,
                level=Level.INFO,
                count=1,
                details={"minutes": minutes, "duration": duration.strip()},
            )
        )
    cycles = (meta.findtext(f"{META}editing-cycles") or "").strip()
    if cycles.isdigit():
        result.add(
            Finding(
                kind=FindingKind.EDITING_CYCLES,
                level=Level.INFO,
                count=int(cycles),
                details={"cycles": int(cycles)},
            )
        )


def _changes(root: Element) -> Finding | None:
    kinds: Counter[str] = Counter()
    authors: Counter[str] = Counter()
    dates: list[str] = []
    for region in root.iter(f"{TEXT}changed-region"):
        for change in region:
            kind = _CHANGES.get(change.tag)
            if kind is None:
                continue
            kinds[kind] += 1
            info = change.find(f"{OFFICE}change-info")
            if info is not None:
                authors[info.findtext(f"{DC}creator") or ""] += 1
                if info.findtext(f"{DC}date"):
                    dates.append(info.findtext(f"{DC}date") or "")
    if not kinds:
        return None
    details: dict[str, str | int] = dict(kinds)
    if joined(authors):
        details["authors"] = joined(authors)
    if dates:
        details["first_date"], details["last_date"] = min(dates), max(dates)
    return Finding(
        kind=FindingKind.TRACKED_CHANGES, level=Level.REVIEW, count=kinds.total(), details=details
    )


def _packages(archive: zipfile.ZipFile, result: FormatResult) -> None:
    names = archive.namelist()
    objects = sorted({n.split("/")[0] for n in names if n.startswith("Object ") and "/" in n})
    if objects:
        result.add(
            Finding(
                kind=FindingKind.EMBEDDED_OBJECTS,
                level=Level.INFO,
                count=len(objects),
                details={"parts": ", ".join(objects)},
            )
        )
    macros = sorted(
        n
        for n in names
        if n.startswith(("Basic/", "Scripts/"))
        and n.endswith((".xml", ".js", ".py", ".bsh"))
        and not n.endswith(("script-lc.xml", "script-lb.xml", "dialog-lc.xml", "dialog-lb.xml"))
    )
    if macros:
        result.add(
            Finding(
                kind=FindingKind.MACROS,
                level=Level.REVIEW,
                count=len(macros),
                details={"parts": ", ".join(macros)},
            )
        )


def inspect_odt(archive: zipfile.ZipFile) -> FormatResult:
    roots: dict[str, Element] = {}
    for name in TEXT_PARTS:
        data = read_member(archive, name)
        if data is not None:
            roots[name] = parse_xml(data, name)
    if "content.xml" not in roots:
        raise DocumentError("not an ODT file: content.xml is missing")
    styles = _Styles()
    for root in reversed(roots.values()):
        styles.read(root)
    result = FormatResult()
    hidden, white, tiny = Passages(), Passages(), Passages()
    annotations: Counter[str] = Counter()
    changes: list[Finding] = []
    for name, root in roots.items():
        scan = _PartScan(name, styles, hidden, white, tiny)
        scan.scan(root)
        result.segments += scan.segments
        for annotation in root.iter(f"{OFFICE}annotation"):
            annotations[annotation.findtext(f"{DC}creator") or ""] += 1
        change = _changes(root)
        if change is not None:
            changes.append(change)
        for section in root.iter(f"{TEXT}section"):
            if section.get(f"{TEXT}display") in {"none", "condition"}:
                hidden.add(Location(part=name), "".join(section.itertext()))
    _meta(archive, result)
    result.findings += changes
    if annotations:
        details: dict[str, str | int] = (
            {"authors": joined(annotations)} if joined(annotations) else {}
        )
        result.add(
            Finding(
                kind=FindingKind.COMMENTS,
                level=Level.REVIEW,
                count=annotations.total(),
                details=details,
            )
        )
    result.add(hidden.finding(FindingKind.HIDDEN_TEXT, Level.REVIEW))
    result.add(white.finding(FindingKind.WHITE_TEXT, Level.REVIEW))
    result.add(tiny.finding(FindingKind.TINY_TEXT, Level.REVIEW))
    _packages(archive, result)
    return result
