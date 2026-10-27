"""Find invisible, unusual and mixed-script characters in text (ADR 006).

The scanner works on *segments*: a paragraph of a word-processing document, a line of a
text file or a page of a PDF. Bidirectional controls are balanced per segment, because the
Unicode bidi algorithm resets at the end of each paragraph.

Nothing here changes the text; occurrences show invisible characters as ``[U+XXXX]``.
"""

import struct
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Final

import regex

from draftwitness.modules.pre.inspect.models import (
    MAX_OCCURRENCES,
    MAX_SAMPLE,
    CodePoint,
    Finding,
    FindingKind,
    Level,
    Location,
    Occurrence,
)

CONTEXT: Final = 25
"""Characters of context kept on each side of an occurrence."""
RUN_SHOWN: Final = 3

# C2PA 2.4 Appendix A.8 text wrapper, as implemented by encypherai/c2pa-text (MIT):
# U+FEFF, then variation selectors encoding magic(8) + version(1) + length(4, big-endian)
# + a JUMBF manifest store.
C2PA_MAGIC: Final = b"C2PATXT\0"
_C2PA_HEADER: Final = struct.Struct("!8sBI")

BOM: Final = 0xFEFF
SOFT_HYPHEN: Final = 0x00AD
JOINERS: Final = frozenset({0x200C, 0x200D})
BIDI_EMBED_OPEN: Final = frozenset({0x202A, 0x202B, 0x202D, 0x202E})
BIDI_OVERRIDES: Final = frozenset({0x202D, 0x202E})
BIDI_POP: Final = 0x202C
BIDI_ISOLATE_OPEN: Final = frozenset({0x2066, 0x2067, 0x2068})
BIDI_ISOLATE_POP: Final = 0x2069
BIDI_MARKS: Final = frozenset({0x200E, 0x200F, 0x061C})
BIDI: Final = BIDI_EMBED_OPEN | BIDI_ISOLATE_OPEN | BIDI_MARKS | {BIDI_POP, BIDI_ISOLATE_POP}
NO_BREAK_SPACES: Final = frozenset({0x00A0, 0x202F})
BLANK_FILLERS: Final = frozenset({0x115F, 0x1160, 0x2800, 0x3164, 0xFFA0})
WAVING_BLACK_FLAG: Final = 0x1F3F4
CANCEL_TAG: Final = 0xE007F
GREEK_LOOKALIKES: Final = frozenset(
    "\u0391\u0392\u0395\u0396\u0397\u0399\u039a\u039c\u039d\u039f\u03a1\u03a4\u03a5\u03a7"
    "\u03bf\u03b9\u03c1\u03bd\u03c5"
)
"""Greek letters that look like Latin ones: capital alpha, beta, epsilon, zeta, eta, iota,
kappa, mu, nu, omicron, rho, tau, upsilon and chi; small omicron, iota, rho, nu and upsilon.
Other Greek letters next to Latin ones (μm, β-cells) are ordinary scientific notation and
are not reported."""

_WORD = regex.compile(r"\p{L}[\p{L}\p{M}]*")
_SCRIPTS: Final = {
    "Latin": regex.compile(r"\p{Script=Latin}"),
    "Greek": regex.compile(r"\p{Script=Greek}"),
    "Cyrillic": regex.compile(r"\p{Script=Cyrillic}"),
}


@dataclass(frozen=True)
class Segment:
    location: Location
    text: str


def is_variation_selector(cp: int) -> bool:
    return 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF


def is_tag(cp: int) -> bool:
    return 0xE0000 <= cp <= 0xE007F


def _vs_byte(cp: int) -> int:
    return cp - 0xFE00 if cp <= 0xFE0F else cp - 0xE0100 + 16


def _invisible(ch: str) -> bool:
    cp = ord(ch)
    category = unicodedata.category(ch)
    return (
        category in {"Cf", "Co", "Cn", "Zl", "Zp"}
        or (category == "Cc" and ch not in "\t\n\r")
        or (category == "Zs" and ch != " ")
        or is_variation_selector(cp)
        or cp in BLANK_FILLERS
    )


def visible(text: str) -> str:
    """``text`` with each invisible or unusual character written as ``[U+XXXX]``.

    A run of more than :data:`RUN_SHOWN` such characters is shortened to its first code point
    and the number of the others, for example ``[U+E0069…+14]``.
    """
    out: list[str] = []
    run: list[int] = []

    def flush() -> None:
        if len(run) > RUN_SHOWN:
            out.append(f"[U+{run[0]:04X}…+{len(run) - 1}]")
        else:
            out.extend(f"[U+{cp:04X}]" for cp in run)
        run.clear()

    for ch in text:
        if _invisible(ch):
            run.append(ord(ch))
            continue
        flush()
        out.append(" " if ch in "\t\n\r" else ch)
    flush()
    return "".join(out)


def code_name(cp: int) -> str:
    name = unicodedata.name(chr(cp), "")
    if name:
        return name
    category = unicodedata.category(chr(cp))
    return {"Cc": "CONTROL", "Co": "PRIVATE USE", "Cn": "UNASSIGNED"}.get(category, "")


def _context(text: str, start: int, end: int) -> str:
    before = text[max(0, start - CONTEXT) : start]
    after = text[end : end + CONTEXT]
    middle = visible(text[start:end])
    prefix = "…" if start > CONTEXT else ""
    suffix = "…" if end + CONTEXT < len(text) else ""
    return f"{prefix}{visible(before)}{middle}{visible(after)}{suffix}"


@dataclass
class _Tally:
    count: int = 0
    code_points: Counter[int] = field(default_factory=Counter)
    occurrences: list[Occurrence] = field(default_factory=list)
    details: dict[str, str | int] = field(default_factory=dict)

    def add(self, location: Location, text: str | None, cps: Iterable[int], n: int = 1) -> None:
        self.count += n
        self.code_points.update(cps)
        if len(self.occurrences) < MAX_OCCURRENCES:
            self.occurrences.append(Occurrence(location=location, text=text))

    def sample(self, key: str, value: str) -> None:
        current = str(self.details.get(key, ""))
        if len(current) < MAX_SAMPLE:
            joined = f"{current} {value}" if current else value
            self.details[key] = joined[:MAX_SAMPLE]


LEVELS: Final[dict[FindingKind, Level]] = {
    FindingKind.FORMAT_CHARACTERS: Level.REVIEW,
    FindingKind.JOINERS: Level.INFO,
    FindingKind.SOFT_HYPHENS: Level.INFO,
    FindingKind.BIDI_CONTROLS: Level.INFO,
    FindingKind.BIDI_OVERRIDES: Level.REVIEW,
    FindingKind.BIDI_UNBALANCED: Level.REVIEW,
    FindingKind.TAG_CHARACTERS: Level.REVIEW,
    FindingKind.EMOJI_TAG_FLAGS: Level.INFO,
    FindingKind.VARIATION_SELECTORS: Level.INFO,
    FindingKind.HIDDEN_DATA: Level.REVIEW,
    FindingKind.C2PA_MANIFEST: Level.REVIEW,
    FindingKind.CONTROL_CHARACTERS: Level.REVIEW,
    FindingKind.PRIVATE_USE: Level.INFO,
    FindingKind.UNASSIGNED: Level.REVIEW,
    FindingKind.UNUSUAL_SPACES: Level.REVIEW,
    FindingKind.NO_BREAK_SPACES: Level.INFO,
    FindingKind.BLANK_FILLERS: Level.REVIEW,
    FindingKind.LINE_SEPARATORS: Level.INFO,
    FindingKind.MIXED_SCRIPT_WORDS: Level.REVIEW,
    FindingKind.BYTE_ORDER_MARK: Level.INFO,
}


_BY_CODE_POINT: Final[dict[int, FindingKind]] = {
    SOFT_HYPHEN: FindingKind.SOFT_HYPHENS,
    **dict.fromkeys(JOINERS, FindingKind.JOINERS),
    **dict.fromkeys(BIDI, FindingKind.BIDI_CONTROLS),
    **dict.fromkeys(BIDI_OVERRIDES, FindingKind.BIDI_OVERRIDES),
    **dict.fromkeys(NO_BREAK_SPACES, FindingKind.NO_BREAK_SPACES),
    **dict.fromkeys(BLANK_FILLERS, FindingKind.BLANK_FILLERS),
}
_BY_CATEGORY: Final = {
    "Cf": FindingKind.FORMAT_CHARACTERS,
    "Cc": FindingKind.CONTROL_CHARACTERS,
    "Co": FindingKind.PRIVATE_USE,
    "Cn": FindingKind.UNASSIGNED,
    "Zl": FindingKind.LINE_SEPARATORS,
    "Zp": FindingKind.LINE_SEPARATORS,
    "Zs": FindingKind.UNUSUAL_SPACES,
}


def _single_kind(cp: int) -> FindingKind | None:
    """The finding kind for a character examined on its own, or ``None`` if ordinary."""
    kind = _BY_CODE_POINT.get(cp)
    return kind if kind is not None else _BY_CATEGORY.get(unicodedata.category(chr(cp)))


def decode_c2pa(data: bytes) -> dict[str, str | int] | None:
    """Header facts of a C2PA text wrapper, or ``None`` if ``data`` is not one."""
    if len(data) < _C2PA_HEADER.size or not data.startswith(C2PA_MAGIC):
        return None
    _, version, length = _C2PA_HEADER.unpack(data[: _C2PA_HEADER.size])
    return {
        "version": version,
        "declared_bytes": length,
        "bytes": len(data) - _C2PA_HEADER.size,
    }


def _run_end(text: str, start: int, test: Callable[[int], bool]) -> int:
    end = start
    while end < len(text) and test(ord(text[end])):
        end += 1
    return end


class _Scanner:
    def __init__(self) -> None:
        self.tallies: dict[FindingKind, _Tally] = {}

    def tally(self, kind: FindingKind) -> _Tally:
        return self.tallies.setdefault(kind, _Tally())

    def _variation_run(self, segment: Segment, start: int, end: int, prefixed: bool) -> None:
        text = segment.text
        run = [ord(ch) for ch in text[start:end]]
        data = bytes(_vs_byte(cp) for cp in run)
        where = start - 1 if prefixed else start
        c2pa = decode_c2pa(data)
        if c2pa is not None:
            tally = self.tally(FindingKind.C2PA_MANIFEST)
            tally.add(segment.location, _context(text, where, end), [])
            for key, value in c2pa.items():
                tally.details[key] = int(tally.details.get(key, 0)) + int(value)
            return
        has_base = start > 0 and not _invisible(text[start - 1])
        if len(run) == 1 and has_base:
            self.tally(FindingKind.VARIATION_SELECTORS).add(
                segment.location, _context(text, start, end), run
            )
            return
        if prefixed:
            self.tally(FindingKind.FORMAT_CHARACTERS).add(
                segment.location, _context(text, where, start), [BOM]
            )
        tally = self.tally(FindingKind.HIDDEN_DATA)
        tally.add(segment.location, _context(text, start, end), run, n=len(run))
        tally.details["bytes"] = int(tally.details.get("bytes", 0)) + len(data)
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            return
        if decoded.isprintable():
            tally.sample("decoded", decoded)

    def _tag_run(self, segment: Segment, start: int, end: int) -> None:
        text = segment.text
        run = [ord(ch) for ch in text[start:end]]
        flag = start > 0 and ord(text[start - 1]) == WAVING_BLACK_FLAG and run[-1] == CANCEL_TAG
        if flag:
            self.tally(FindingKind.EMOJI_TAG_FLAGS).add(
                segment.location, _context(text, start - 1, end), run
            )
            return
        decoded = "".join(chr(cp - 0xE0000) for cp in run if 0x20 <= cp - 0xE0000 <= 0x7E)
        tally = self.tally(FindingKind.TAG_CHARACTERS)
        tally.add(segment.location, _context(text, start, end), run, n=len(run))
        if decoded:
            tally.sample("decoded", decoded)

    def _bidi_balance(self, segment: Segment) -> None:
        stack: list[tuple[bool, int]] = []  # (is_isolate, offset)
        unmatched: list[int] = []
        for offset, ch in enumerate(segment.text):
            cp = ord(ch)
            if cp in BIDI_EMBED_OPEN:
                stack.append((False, offset))
            elif cp in BIDI_ISOLATE_OPEN:
                stack.append((True, offset))
            elif cp == BIDI_POP:
                if stack and not stack[-1][0]:
                    stack.pop()
                else:
                    unmatched.append(offset)
            elif cp == BIDI_ISOLATE_POP:
                if any(isolate for isolate, _ in stack):
                    while not stack.pop()[0]:
                        pass
                else:
                    unmatched.append(offset)
        unmatched += [offset for _, offset in stack]
        if unmatched:
            first = min(unmatched)
            cps = [ord(segment.text[offset]) for offset in unmatched]
            self.tally(FindingKind.BIDI_UNBALANCED).add(
                segment.location, _context(segment.text, first, first + 1), cps, n=len(cps)
            )

    def _mixed_scripts(self, segment: Segment) -> None:
        for match in _WORD.finditer(segment.text):
            word = match.group()
            if word.isascii():
                continue
            scripts: dict[str, list[str]] = {}
            for ch in word:
                for script, pattern in _SCRIPTS.items():
                    if pattern.match(ch):
                        scripts.setdefault(script, []).append(ch)
            if len(scripts) < 2:
                continue
            greek = scripts.get("Greek", [])
            if set(scripts) == {"Latin", "Greek"} and not GREEK_LOOKALIKES.intersection(greek):
                continue
            majority = max(scripts, key=lambda s: len(scripts[s]))
            odd = [
                ord(ch) for script, chars in scripts.items() if script != majority for ch in chars
            ]
            marked = "".join(f"[U+{ord(ch):04X}]" if ord(ch) in odd else ch for ch in word)
            self.tally(FindingKind.MIXED_SCRIPT_WORDS).add(segment.location, marked, odd)

    def scan(self, segment: Segment, *, starts_file: bool) -> None:
        text = segment.text
        if not text:
            return
        i = 0
        if starts_file and ord(text[0]) == BOM:
            self.tally(FindingKind.BYTE_ORDER_MARK).add(segment.location, None, [BOM])
            i = 1
        while i < len(text):
            cp = ord(text[i])
            if cp == BOM and i + 1 < len(text) and is_variation_selector(ord(text[i + 1])):
                end = _run_end(text, i + 1, is_variation_selector)
                self._variation_run(segment, i + 1, end, prefixed=True)
                i = end
            elif is_variation_selector(cp):
                end = _run_end(text, i, is_variation_selector)
                self._variation_run(segment, i, end, prefixed=False)
                i = end
            elif is_tag(cp):
                end = _run_end(text, i, is_tag)
                self._tag_run(segment, i, end)
                i = end
            else:
                ordinary = 0x20 <= cp <= 0x7E or text[i] in "\t\n\r"
                kind = None if ordinary else _single_kind(cp)
                if kind is not None:
                    self.tally(kind).add(segment.location, _context(text, i, i + 1), [cp])
                i += 1
        if any(ord(ch) in BIDI for ch in text):
            self._bidi_balance(segment)
        self._mixed_scripts(segment)

    def findings(self) -> list[Finding]:
        result = []
        for kind in FindingKind:
            tally = self.tallies.get(kind)
            if tally is None or tally.count == 0:
                continue
            code_points = [
                CodePoint(code=f"U+{cp:04X}", name=code_name(cp), count=n)
                for cp, n in sorted(tally.code_points.items())
            ]
            result.append(
                Finding(
                    kind=kind,
                    level=LEVELS[kind],
                    count=tally.count,
                    code_points=code_points,
                    occurrences=tally.occurrences,
                    details=tally.details,
                )
            )
        return result


def scan_characters(segments: Iterable[Segment], *, text_file: bool = False) -> list[Finding]:
    """Character findings for ``segments``, in :class:`FindingKind` order.

    With ``text_file``, a byte-order mark at the very start is reported as such rather than
    as a zero-width no-break space.
    """
    scanner = _Scanner()
    for index, segment in enumerate(segments):
        scanner.scan(segment, starts_file=text_file and index == 0)
    return scanner.findings()
