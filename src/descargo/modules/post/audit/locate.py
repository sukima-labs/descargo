"""Find a detector's matched passage inside the student's document.

Detectors and our extractor see slightly different text (curly vs straight quotes, line
breaks, hyphenation, case), so both sides are normalised and an index maps every
normalised character back to the original. An exact normalised match is tried first; then
a fuzzy match anchored on the passage's first and last words and checked with difflib.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from typing import Final

# Typographic quotes and dashes, folded to ASCII for matching only.
_FOLD: Final = str.maketrans(
    {
        "\u201c": '"',  # left double quotation mark
        "\u201d": '"',  # right double quotation mark
        "\u201e": '"',  # double low-9 quotation mark
        "\u00ab": '"',  # left-pointing double angle quotation mark
        "\u00bb": '"',  # right-pointing double angle quotation mark
        "\u2018": "'",  # left single quotation mark
        "\u2019": "'",  # right single quotation mark
        "\u201a": "'",  # single low-9 quotation mark
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
    }
)
# Soft hyphen, zero-width space/non-joiner/joiner, word joiner, byte order mark.
_IGNORED: Final = frozenset({"\u00ad", "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"})
_ANCHOR_WORDS: Final = 4
_MIN_FUZZY_WORDS: Final = 8
_MIN_RATIO: Final = 0.85
_LENGTH_SLACK: Final = 0.3


@dataclass(frozen=True)
class Normalized:
    text: str
    index: tuple[int, ...]
    """``index[i]`` is the offset in the original text of normalised character ``i``."""


def normalize(text: str) -> Normalized:
    chars: list[str] = []
    index: list[int] = []
    previous_space = True
    length = len(text)
    i = 0
    while i < length:
        char = text[i]
        if char in _IGNORED:
            i += 1
            continue
        if char == "-" and i + 1 < length and text[i + 1] == "\n" and i and text[i - 1].isalpha():
            i += 2  # a word hyphenated across a line break
            continue
        if char.isspace():
            if not previous_space:
                chars.append(" ")
                index.append(i)
                previous_space = True
            i += 1
            continue
        for folded in char.translate(_FOLD).casefold():
            chars.append(folded)
            index.append(i)
        previous_space = False
        i += 1
    return Normalized("".join(chars), tuple(index))


class LocateMethod(StrEnum):
    EXACT = "exact"
    FUZZY = "fuzzy"


@dataclass(frozen=True)
class Location:
    start: int
    end: int
    method: LocateMethod
    occurrences: int
    """How many places matched; when more than one, the one nearest the report's offset
    (or the first) was used."""
    ratio: float = 1.0


def _span(haystack: Normalized, start: int, length: int) -> tuple[int, int]:
    return haystack.index[start], haystack.index[start + length - 1] + 1


def _occurrences(haystack: str, needle: str) -> list[int]:
    found: list[int] = []
    position = haystack.find(needle)
    while position != -1:
        found.append(position)
        position = haystack.find(needle, position + 1)
    return found


def _fuzzy(needle: str, haystack: Normalized) -> Location | None:
    words = needle.split(" ")
    if len(words) < _MIN_FUZZY_WORDS:
        return None
    head = " ".join(words[:_ANCHOR_WORDS])
    tail = " ".join(words[-_ANCHOR_WORDS:])
    best: tuple[float, int, int] | None = None
    text = haystack.text
    for start in _occurrences(text, head):
        low = start + int(len(needle) * (1 - _LENGTH_SLACK))
        high = start + int(len(needle) * (1 + _LENGTH_SLACK))
        for tail_start in _occurrences(text[low:high], tail):
            end = low + tail_start + len(tail)
            ratio = SequenceMatcher(None, needle, text[start:end], autojunk=False).ratio()
            if ratio >= _MIN_RATIO and (best is None or ratio > best[0]):
                best = (ratio, start, end)
    if best is None:
        return None
    ratio, start, end = best
    original_start, original_end = _span(haystack, start, end - start)
    return Location(original_start, original_end, LocateMethod.FUZZY, 1, round(ratio, 3))


def locate(passage: str, haystack: Normalized, *, near: int | None = None) -> Location | None:
    """Where ``passage`` occurs in the original text behind ``haystack``."""
    needle = normalize(passage).text.strip(" \"'")
    if not needle:
        return None
    found = _occurrences(haystack.text, needle)
    if not found:
        return _fuzzy(needle, haystack)
    spans = [_span(haystack, position, len(needle)) for position in found]
    chosen = spans[0] if near is None else min(spans, key=lambda span: abs(span[0] - near))
    return Location(chosen[0], chosen[1], LocateMethod.EXACT, len(spans))
