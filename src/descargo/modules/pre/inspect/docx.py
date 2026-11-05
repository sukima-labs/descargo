"""Inspect a DOCX file: text parts, properties, RSIDs, revisions, hidden content, fields.

Reads the ZIP + XML structure directly (ADR 006): python-docx hides exactly what an
inspector needs, such as deleted text, RSIDs and field codes.
"""

import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Final
from xml.etree.ElementTree import Element

from descargo.core.documents.archive import DocumentError, parse_xml, read_member
from descargo.modules.pre.inspect.chars import Segment
from descargo.modules.pre.inspect.common import (
    FormatResult,
    Passages,
    joined,
    leaf_fields,
    metadata_field,
)
from descargo.modules.pre.inspect.models import Finding, FindingKind, Level, Location

W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R: Final = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL: Final = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_MC_FALLBACK: Final = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
_VT: Final = "{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}"
TEXT_PARTS: Final = re.compile(
    r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"
)
BODY: Final = "word/document.xml"
TINY_HALF_POINTS: Final = 4
"""Runs smaller than 2 pt (``w:sz`` is in half-points) are reported as tiny."""
_FALSE: Final = frozenset({"0", "false", "off"})
_WHITE: Final = frozenset({"FFFFFF", "ffffff"})
_REVISIONS: Final = {
    f"{W}ins": "insertions",
    f"{W}del": "deletions",
    f"{W}moveFrom": "moves",
    f"{W}rPrChange": "formatting",
    f"{W}pPrChange": "formatting",
}


def _val(element: Element | None) -> str | None:
    return None if element is None else element.get(f"{W}val")


@dataclass(frozen=True)
class _RunProps:
    vanish: bool | None = None
    color: str | None = None
    size: int | None = None
    background: bool | None = None
    """A highlight or shading that is not white, which makes white text readable."""

    @classmethod
    def read(cls, rpr: Element | None) -> "_RunProps":
        if rpr is None:
            return cls()
        vanish_el = rpr.find(f"{W}vanish")
        vanish = None if vanish_el is None else (_val(vanish_el) or "true") not in _FALSE
        size_text = _val(rpr.find(f"{W}sz"))
        size = int(size_text) if size_text and size_text.isdigit() else None
        highlight = _val(rpr.find(f"{W}highlight"))
        shading = rpr.find(f"{W}shd")
        fill = shading.get(f"{W}fill") if shading is not None else None
        background = None
        if highlight is not None or fill is not None:
            background = (highlight not in {None, "none", "white"}) or (
                fill not in {None, "auto"} and fill not in _WHITE
            )
        return cls(vanish, _val(rpr.find(f"{W}color")), size, background)

    def over(self, base: "_RunProps") -> "_RunProps":
        return _RunProps(
            self.vanish if self.vanish is not None else base.vanish,
            self.color if self.color is not None else base.color,
            self.size if self.size is not None else base.size,
            self.background if self.background is not None else base.background,
        )


@dataclass
class _Styles:
    props: dict[str, _RunProps] = field(default_factory=dict)
    based_on: dict[str, str] = field(default_factory=dict)
    defaults: _RunProps = field(default_factory=_RunProps)
    default_paragraph: str | None = None

    @classmethod
    def read(cls, root: Element | None) -> "_Styles":
        styles = cls()
        if root is None:
            return styles
        default_rpr = root.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
        styles.defaults = _RunProps.read(default_rpr)
        for style in root.iter(f"{W}style"):
            style_id = style.get(f"{W}styleId", "")
            styles.props[style_id] = _RunProps.read(style.find(f"{W}rPr"))
            parent = _val(style.find(f"{W}basedOn"))
            if parent:
                styles.based_on[style_id] = parent
            if style.get(f"{W}type") == "paragraph" and style.get(f"{W}default") in {"1", "true"}:
                styles.default_paragraph = style_id
        return styles

    def resolve(self, style_id: str | None) -> _RunProps:
        props = _RunProps()
        seen: set[str] = set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            props = props.over(self.props.get(style_id, _RunProps()))
            style_id = self.based_on.get(style_id)
        return props


@dataclass
class _PartScan:
    part: str
    styles: _Styles
    segments: list[Segment] = field(default_factory=list)
    hidden: Passages = field(default_factory=Passages)
    white: Passages = field(default_factory=Passages)
    tiny: Passages = field(default_factory=Passages)
    rsid_chars: Counter[str] = field(default_factory=Counter)

    def scan(self, root: Element) -> None:
        self._walk(root, [], Location(part=self.part), _RunProps(), None)

    def paragraph(self, element: Element) -> None:
        location = Location(part=self.part, paragraph=len(self.segments) + 1)
        self.segments.append(Segment(location, ""))
        index = len(self.segments) - 1
        pstyle = _val(element.find(f"{W}pPr/{W}pStyle")) or self.styles.default_paragraph
        base = self.styles.resolve(pstyle).over(self.styles.defaults)
        default_rsid = element.get(f"{W}rsidRDefault") or element.get(f"{W}rsidR")
        parts: list[str] = []
        self._walk(element, parts, location, base, default_rsid)
        self.segments[index] = Segment(location, "".join(parts))

    def _walk(
        self,
        element: Element,
        parts: list[str],
        location: Location,
        base: _RunProps,
        rsid: str | None,
    ) -> None:
        for child in element:
            if child.tag == _MC_FALLBACK:
                continue
            if child.tag == f"{W}p":
                self.paragraph(child)
            elif child.tag == f"{W}r":
                self._run(child, parts, location, base, rsid)
            else:
                self._walk(child, parts, location, base, rsid)

    def _run(
        self,
        run: Element,
        parts: list[str],
        location: Location,
        base: _RunProps,
        rsid: str | None,
    ) -> None:
        rpr = run.find(f"{W}rPr")
        rstyle = _val(rpr.find(f"{W}rStyle")) if rpr is not None else None
        props = _RunProps.read(rpr).over(self.styles.resolve(rstyle)).over(base)
        text: list[str] = []
        for child in run:
            if child.tag in {f"{W}t", f"{W}delText"}:
                text.append(child.text or "")
            elif child.tag == f"{W}tab":
                text.append("\t")
            elif child.tag == f"{W}sym":
                code = child.get(f"{W}char", "")
                if re.fullmatch(r"[0-9A-Fa-f]{1,6}", code):
                    text.append(chr(int(code, 16)))
            elif child.tag != f"{W}rPr":
                inner: list[str] = []
                self._walk(child, inner, location, base, rsid)
                text.extend(inner)
        content = "".join(text)
        parts.append(content)
        if props.vanish:
            self.hidden.add(location, content)
        elif props.color in _WHITE and not props.background:
            self.white.add(location, content)
        if props.size is not None and props.size < TINY_HALF_POINTS and not props.vanish:
            self.tiny.add(location, content)
        if self.part == BODY and content.strip():
            self.rsid_chars[run.get(f"{W}rsidR") or rsid or ""] += len(content)


def _rels(archive: zipfile.ZipFile, name: str) -> dict[str, str]:
    data = read_member(archive, name)
    if data is None:
        return {}
    return {
        rel.get("Id", ""): rel.get("Target", "")
        for rel in parse_xml(data, name).iter(f"{_PKG_REL}Relationship")
    }


def _field_type(instruction: str) -> str:
    words = instruction.split()
    if not words:
        return ""
    head = words[0].upper()
    if head == "ADDIN" and len(words) > 1:
        return f"ADDIN {words[1]}"
    return head


def _fields(root: Element) -> Counter[str]:
    types: Counter[str] = Counter()
    stack: list[list[str]] = []
    for element in root.iter():
        if element.tag == f"{W}fldSimple":
            types[_field_type(element.get(f"{W}instr", ""))] += 1
        elif element.tag == f"{W}fldChar":
            kind = element.get(f"{W}fldCharType")
            if kind == "begin":
                stack.append([])
            elif kind in {"separate", "end"} and stack:
                instruction = "".join(stack[-1])
                if kind == "end":
                    stack.pop()
                else:
                    stack[-1] = []
                if instruction.strip():
                    types[_field_type(instruction)] += 1
        elif element.tag == f"{W}instrText" and stack:
            stack[-1].append(element.text or "")
    types.pop("", None)
    return types


@dataclass
class _Revisions:
    kinds: Counter[str] = field(default_factory=Counter)
    authors: Counter[str] = field(default_factory=Counter)
    dates: list[str] = field(default_factory=list)

    def scan(self, root: Element) -> None:
        for element in root.iter():
            kind = _REVISIONS.get(element.tag)
            if kind is None:
                continue
            self.kinds[kind] += 1
            self.authors[element.get(f"{W}author", "")] += 1
            if element.get(f"{W}date"):
                self.dates.append(element.get(f"{W}date", ""))

    def finding(self) -> Finding | None:
        total = sum(self.kinds.values())
        if not total:
            return None
        details: dict[str, str | int] = dict(self.kinds)
        if joined(self.authors):
            details["authors"] = joined(self.authors)
        if self.dates:
            details["first_date"] = min(self.dates)
            details["last_date"] = max(self.dates)
        return Finding(
            kind=FindingKind.TRACKED_CHANGES, level=Level.REVIEW, count=total, details=details
        )


def _properties(archive: zipfile.ZipFile, result: FormatResult) -> None:
    for name in ("docProps/core.xml", "docProps/app.xml"):
        data = read_member(archive, name)
        if data is not None:
            result.metadata += leaf_fields(parse_xml(data, name), name)
    custom = read_member(archive, "docProps/custom.xml")
    if custom is not None:
        for prop in parse_xml(custom, "docProps/custom.xml"):
            value = next((child.text or "" for child in prop if child.tag.startswith(_VT)), "")
            result.metadata.append(
                metadata_field("docProps/custom.xml", prop.get("name", ""), value)
            )
    minutes = next(
        (
            m.value
            for m in result.metadata
            if m.part == "docProps/app.xml" and m.name == "app:TotalTime"
        ),
        None,
    )
    if minutes is not None and minutes.isdigit():
        result.add(
            Finding(
                kind=FindingKind.EDITING_TIME,
                level=Level.INFO,
                count=1,
                details={"minutes": int(minutes)},
            )
        )


def _rsids(archive: zipfile.ZipFile, body: _PartScan) -> Finding:
    data = read_member(archive, "word/settings.xml")
    in_settings = 0
    if data is not None:
        in_settings = sum(1 for _ in parse_xml(data, "word/settings.xml").iter(f"{W}rsid"))
    sessions = Counter({rsid: n for rsid, n in body.rsid_chars.items() if rsid})
    total = sum(body.rsid_chars.values())
    details: dict[str, str | int] = {
        "in_settings": in_settings,
        "in_body_text": len(sessions),
        "body_characters": total,
    }
    if sessions and total:
        details["largest_share"] = round(sessions.most_common(1)[0][1] / total * 100)
    if body.rsid_chars.get(""):
        details["characters_without_rsid"] = body.rsid_chars[""]
    return Finding(kind=FindingKind.RSIDS, level=Level.INFO, count=in_settings, details=details)


def _attached_template(archive: zipfile.ZipFile) -> Finding | None:
    data = read_member(archive, "word/settings.xml")
    if data is None:
        return None
    element = parse_xml(data, "word/settings.xml").find(f"{W}attachedTemplate")
    if element is None:
        return None
    target = _rels(archive, "word/_rels/settings.xml.rels").get(element.get(f"{R}id", ""), "")
    return Finding(
        kind=FindingKind.ATTACHED_TEMPLATE,
        level=Level.INFO,
        count=1,
        details={"target": target} if target else {},
    )


def _packages(archive: zipfile.ZipFile, body_root: Element, result: FormatResult) -> None:
    rels = _rels(archive, "word/_rels/document.xml.rels")
    chunks = [rels.get(el.get(f"{R}id", ""), "") for el in body_root.iter(f"{W}altChunk")]
    if chunks:
        result.add(
            Finding(
                kind=FindingKind.ALT_CHUNKS,
                level=Level.REVIEW,
                count=len(chunks),
                details={"parts": ", ".join(sorted(filter(None, chunks)))},
            )
        )
    names = archive.namelist()
    embedded = sorted(n for n in names if n.startswith("word/embeddings/"))
    if embedded:
        result.add(
            Finding(
                kind=FindingKind.EMBEDDED_OBJECTS,
                level=Level.INFO,
                count=len(embedded),
                details={"parts": ", ".join(embedded)},
            )
        )
    macros = sorted(n for n in names if n.lower().endswith("vbaproject.bin"))
    if macros:
        result.add(
            Finding(
                kind=FindingKind.MACROS,
                level=Level.REVIEW,
                count=len(macros),
                details={"parts": ", ".join(macros)},
            )
        )


def inspect_docx(archive: zipfile.ZipFile) -> FormatResult:
    body_data = read_member(archive, BODY)
    if body_data is None:
        raise DocumentError("not a DOCX file: word/document.xml is missing")
    styles_data = read_member(archive, "word/styles.xml")
    styles = _Styles.read(parse_xml(styles_data, "word/styles.xml") if styles_data else None)
    result = FormatResult()
    revisions = _Revisions()
    fields: Counter[str] = Counter()
    hidden, white, tiny = Passages(), Passages(), Passages()
    body = _PartScan(BODY, styles, hidden=hidden, white=white, tiny=tiny)
    body_root = parse_xml(body_data, BODY)
    comments: Counter[str] = Counter()
    parts = sorted(
        (name for name in archive.namelist() if TEXT_PARTS.match(name)),
        key=lambda n: (n != BODY, n),
    )
    for name in parts:
        if name == BODY:
            scan, root = body, body_root
        else:
            root = parse_xml(read_member(archive, name) or b"", name)
            scan = _PartScan(name, styles, hidden=hidden, white=white, tiny=tiny)
        scan.scan(root)
        result.segments += scan.segments
        revisions.scan(root)
        fields.update(_fields(root))
        if name == "word/comments.xml":
            comments.update(c.get(f"{W}author", "") for c in root.iter(f"{W}comment"))
    _properties(archive, result)
    result.add(_rsids(archive, body))
    result.add(revisions.finding())
    if comments:
        details: dict[str, str | int] = {"authors": joined(comments)} if joined(comments) else {}
        result.add(
            Finding(
                kind=FindingKind.COMMENTS,
                level=Level.REVIEW,
                count=sum(comments.values()),
                details=details,
            )
        )
    result.add(hidden.finding(FindingKind.HIDDEN_TEXT, Level.REVIEW))
    result.add(white.finding(FindingKind.WHITE_TEXT, Level.REVIEW))
    result.add(tiny.finding(FindingKind.TINY_TEXT, Level.REVIEW))
    if fields:
        result.add(
            Finding(
                kind=FindingKind.FIELDS,
                level=Level.INFO,
                count=fields.total(),
                details=dict(sorted(fields.items())),
            )
        )
    _packages(archive, body_root, result)
    result.add(_attached_template(archive))
    return result
