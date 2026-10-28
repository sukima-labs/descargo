"""The Compilatio Magister+ layout of 2026 ("Informe de análisis" or "Certificado de análisis").

Section 1 sums up the results and says which ones count in the suspicious-text percentage
("Incluido en el porcentaje de textos sospechosos") and which do not. Section 2 lists the
sources in tables whose text comes out of the PDF a column at a time, so the rows are put
back together from where each piece is drawn. Section 3, in the full report only, reproduces
the document; Compilatio underlines what it attributes to AI with a thin bar in its AI
colour, and highlights what matches a source behind the text.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Final

from pypdf import PdfReader

from draftwitness.adapters.base import AdapterError
from draftwitness.adapters.compilatio.common import (
    AI_COLOUR,
    NUMBER,
    Download,
    Words,
    after,
    build_report,
    count,
    day,
    joined_runs,
    overlap_warnings,
    percent_before,
    same,
    submission,
    value,
)
from draftwitness.core.report_schema import (
    AiSegment,
    AiWriting,
    Report,
    Similarity,
    Source,
    SourceKind,
)

_INDICATORS: Final = ("similarity", "ai", "unrecognised_languages", "quoted")
_ROW_REACH: Final = 16.0
"""How far above or below a row's number, in points, the row's other lines are drawn."""
_UNDERLINE_GAP: Final = 6.0
"""How far below the text's baseline, in points, an underline may start."""
_UNDERLINE_HEIGHT: Final = 2.5
_HEX = re.compile(r"#[0-9a-f]{6}")


def recognises(lines: list[str], words: Words) -> bool:
    head = lines[:3]
    return any(line in head for line in (words["report"], words["certificate"])) and any(
        line.startswith(words["product"]) for line in head
    )


def _results(head: list[str], words: Words) -> tuple[dict[str, tuple[float, bool]], dict[str, Any]]:
    """The section-1 percentages, keyed like ``labels.yaml``, and what goes with them: for
    each, whether it counts in the suspicious-text percentage, and the similarity split."""
    labels = {words[key]: key for key in _INDICATORS}
    results: dict[str, tuple[float, bool]] = {}
    details: dict[str, Any] = {"included_in_suspicious": {}}
    included: bool | None = None
    current: str | None = None
    split = re.compile(
        rf"^{words['syntactic']}\s*{NUMBER}\s*{words['semantic']}\s*"
        rf"(?:{NUMBER}|{words['not_measured']})$"
    )
    for line in head:
        if line in {words["included"], words["not_included"]}:
            included = line == words["included"]
        elif line in labels:
            current = labels[line]
            if included is not None:
                details["included_in_suspicious"][current] = included
        elif (match := split.match(line)) is not None:
            details["syntactic_similarity_percent"] = value(match)[0]
            details["semantic_similarity_percent"] = value(match, 3)[0] if match.group(4) else None
        elif current is not None and (match := re.fullmatch(NUMBER, line)) is not None:
            results.setdefault(current, value(match))
            current = None
    suspicious = percent_before(" ".join(head), words["suspicious"])
    if suspicious is not None:
        results["suspicious"] = suspicious
    return results, details


@dataclass
class _Piece:
    page: int
    y: float
    x: float
    fill: tuple[float, ...] | None
    text: str


@dataclass
class _Bar:
    """A thin filled rectangle: Compilatio's underline."""

    page: int
    left: float
    right: float
    top: float


class _Drawing:
    """Collects, for one page, each piece of text with its position and colour, and the
    thin bars filled in :data:`AI_COLOUR` (a pypdf visitor)."""

    def __init__(self, page: int) -> None:
        self.page = page
        self.fill: tuple[float, ...] | None = None
        self.path: list[tuple[float, float, float, float]] = []
        self.pieces: list[_Piece] = []
        self.bars: list[_Bar] = []

    def before(self, operator: bytes, operands: list[Any], cm: list[float], _tm: object) -> None:
        if operator in {b"rg", b"sc", b"scn", b"g"}:
            values = [float(o) for o in operands if isinstance(o, int | float)]
            self.fill = tuple(values * 3 if operator == b"g" else values) or None
        elif operator == b"re" and len(operands) == 4:
            x, y, w, h = (float(o) for o in operands)
            xs, ys = zip(*(_apply(cm, px, py) for px, py in ((x, y), (x + w, y + h))), strict=True)
            self.path.append((min(xs), max(xs), min(ys), max(ys)))
        elif operator in {b"f", b"F", b"f*"}:
            if same(self.fill, AI_COLOUR):
                self.bars += [
                    _Bar(self.page, left, right, top)
                    for left, right, bottom, top in self.path
                    if top - bottom <= _UNDERLINE_HEIGHT and right - left > 1
                ]
            self.path = []
        elif operator in {b"n", b"S", b"s", b"B", b"B*", b"b", b"b*"}:
            self.path = []

    def text(
        self, content: str, cm: list[float], tm: list[float], _font: object, _size: object
    ) -> None:
        x, y = _apply(cm, tm[4], tm[5])
        text = unicodedata.normalize("NFKC", content).replace("\n", " ")
        self.pieces.append(_Piece(self.page, y, x, self.fill, text))


def _apply(matrix: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def _drawings(reader: PdfReader) -> list[_Drawing]:
    """What is drawn on every page after the first."""
    drawings = []
    for number, page in enumerate(reader.pages[1:], start=2):
        drawing = _Drawing(number)
        page.extract_text(visitor_operand_before=drawing.before, visitor_text=drawing.text)
        drawings.append(drawing)
    return drawings


def _find(pieces: list[_Piece], label: str) -> int | None:
    return next((i for i, piece in enumerate(pieces) if piece.text.strip().startswith(label)), None)


@dataclass
class _Row:
    number: int
    piece: _Piece
    group: str
    texts: list[_Piece] = field(default_factory=list)
    percent: list[_Piece] = field(default_factory=list)


@dataclass
class _Parsed:
    sources: list[Source] = field(default_factory=list)
    groups: dict[str, str] = field(default_factory=dict)
    origins: dict[str, str] = field(default_factory=dict)
    semantic: list[str] = field(default_factory=list)
    mentioned: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _column(piece: _Piece, columns: dict[str, float]) -> str | None:
    """Which column of the current table ``piece`` is in: "number", "percent" or "texts";
    ``None`` outside any table and in the locations column, which holds only drawings."""
    if "descriptions" not in columns:
        return None
    if piece.x < columns["descriptions"] - 4:
        return "number"
    if "locations" in columns and piece.x >= columns["locations"] - 4:
        return None
    if "similarity" in columns and piece.x >= columns["similarity"] - 10:
        return "percent"
    return "texts"


def _rows(pieces: list[_Piece], words: Words) -> list[_Row]:
    """The table rows in ``pieces`` (section 2, top to bottom), each with the pieces drawn
    next to its number. Each table's header row gives its columns."""
    headings = {
        words["main_sources"]: "main",
        words["incidental_sources"]: "incidental",
        words["mentioned_sources"]: "mentioned",
    }
    columns: dict[str, float] = {}
    header_y: tuple[int, float] | None = None
    group = "main"
    rows: list[_Row] = []
    loose: list[tuple[str, _Piece]] = []
    for piece in pieces:
        text = piece.text.strip()
        if not text:
            continue
        heading = next((key for label, key in headings.items() if text.startswith(label)), None)
        if heading is not None:
            group = heading
        elif text == words["number_column"]:
            columns, header_y = {"number": piece.x}, (piece.page, piece.y)
        elif header_y is not None and header_y[0] == piece.page and abs(header_y[1] - piece.y) < 1:
            for key in ("descriptions", "similarity", "locations"):
                if text == words[f"{key}_column"]:
                    columns[key] = piece.x
        elif (column := _column(piece, columns)) == "number":
            if text.isdigit():
                rows.append(_Row(int(text), piece, group))
        elif column is not None:
            loose.append((column, piece))
    for kind, piece in loose:
        near = [row for row in rows if row.piece.page == piece.page]
        nearest = min(near, key=lambda row: abs(row.piece.y - piece.y), default=None)
        if nearest is not None and abs(nearest.piece.y - piece.y) <= _ROW_REACH:
            getattr(nearest, kind).append(piece)
    return rows


def _read_order(pieces: list[_Piece]) -> list[_Piece]:
    return sorted(pieces, key=lambda piece: (piece.page, -round(piece.y, 1), piece.x))


def _shown(pieces: list[_Piece]) -> str:
    """The pieces' text as one line: pieces on one baseline run on, lines join with a space."""
    return " ".join(joined_runs([[(piece.y, piece.text) for piece in pieces]]))


def _source(row: _Row, words: Words, parsed: _Parsed) -> None:
    """The row as a source. Its name is drawn in the row's colour; its URL (without a
    scheme, as shown) and its notes ("Viene de de otro grupo", "Detección semántica") in
    grey."""
    pieces = _read_order(row.texts)
    label = _shown([p for p in pieces if same(p.fill, row.piece.fill or ())])
    if label.startswith(words["locked"]):
        label = label[len(words["locked"]) :].strip()  # the name of a padlock icon
    rest = _shown([p for p in pieces if not same(p.fill, row.piece.fill or ())])
    semantic = re.search(r"\s*".join(map(re.escape, words["semantic_detection"].split())), rest)
    origin = None
    for key in ("from_my_library", "from_another_group"):
        if words[key] in rest:
            origin = key.removeprefix("from_")
            rest = rest.replace(words[key], "")
    if semantic:
        rest = rest.replace(semantic.group(0), "")
    shown = " ".join(_HEX.sub("", rest).split())
    url = shown or None
    if url is not None and ("..." in url or " " in url):
        url = None  # shortened on the report
    percent = re.fullmatch(NUMBER, "".join(p.text for p in _read_order(row.percent)).strip())
    source_id = f"{row.group[0]}{row.number}"
    if source_id in parsed.groups:
        parsed.warnings.append(
            f"Source {row.number} appears twice in one table; the second was ignored."
        )
        return
    if percent is None:
        parsed.warnings.append(f"The percentage of source {row.number} could not be read.")
    kind = SourceKind.UNKNOWN
    if origin is not None or label.startswith(words["other_user_document"]):
        kind = SourceKind.STUDENT_PAPER
    elif shown:
        kind = SourceKind.INTERNET
    parsed.groups[source_id] = row.group
    if origin is not None:
        parsed.origins[source_id] = origin
    if semantic:
        parsed.semantic.append(source_id)
    bound = value(percent) if percent else (None, False)
    parsed.sources.append(
        Source(
            id=source_id,
            rank=row.number,
            label=label or shown or f"{row.number}",
            kind=kind,
            url=url,
            percent=bound[0],
            percent_is_upper_bound=bound[1],
        )
    )


def _tables(drawings: list[_Drawing], words: Words) -> tuple[_Parsed, int | None]:
    """Section 2, and where section 3 starts in the drawn pieces (or ``None``)."""
    parsed = _Parsed()
    pieces = [piece for drawing in drawings for piece in _read_order(drawing.pieces)]
    start = _find(pieces, words["sources_section"])
    end = _find(pieces, words["points_of_interest"])
    if start is None:
        parsed.warnings.append("No source table was found on the report.")
        return parsed, end
    for row in _rows(pieces[start : end if end is not None else len(pieces)], words):
        if row.group == "mentioned":
            cited = _shown(_read_order(row.texts))
            if cited:
                parsed.mentioned.append(cited)
        else:
            _source(row, words, parsed)
    return parsed, end


def _ai_segments(drawings: list[_Drawing], body: _Piece) -> list[AiSegment]:
    """Runs of the document's text with an AI underline, page by page, from section 3 on.
    A run ends at any other text of the document, and at the end of a page. Text left of
    the document's usual left edge (the source numbers in the margin) is skipped."""
    pages = [drawing for drawing in drawings if drawing.page >= body.page]
    starts = Counter(round(p.x) for d in pages for p in d.pieces if p.text.strip())
    left = starts.most_common(1)[0][0] - 10 if starts else 0
    segments: list[AiSegment] = []
    for drawing in pages:
        if not drawing.bars:
            continue
        runs: list[list[tuple[float, str]]] = [[]]
        for piece in drawing.pieces:
            if drawing.page == body.page and piece.y >= body.y:
                continue
            if not piece.text.strip():
                if runs[-1]:
                    runs[-1].append((piece.y, " "))
            elif piece.x < left:
                continue
            elif any(
                bar.left - 2 <= piece.x <= bar.right - 1 and 0 < piece.y - bar.top <= _UNDERLINE_GAP
                for bar in drawing.bars
            ):
                runs[-1].append((piece.y, piece.text))
            elif runs[-1]:
                runs.append([])
        segments += [AiSegment(text=text, page=drawing.page) for text in joined_runs(runs)]
    return segments


def parse(
    reader: PdfReader,
    lines: list[str],
    words: Words,
    language: str,
    download: Download,
) -> Report:
    end = next(
        (i for i, line in enumerate(lines) if line.startswith(words["sources_section"])), None
    )
    head = lines[:end]
    results, details = _results(head, words)
    warnings: list[str] = []
    if "similarity" not in results:
        raise AdapterError("the overall similarity percentage could not be read")
    overall, overall_bound = results["similarity"]
    if overall_bound:
        warnings.append(
            f"The report shows the overall similarity as “<{overall:g}%”; {overall:g}% is used."
        )

    drawings = _drawings(reader)
    parsed, body_at = _tables(drawings, words)
    warnings += parsed.warnings
    if "suspicious" in results and not results["suspicious"][1]:
        warnings += overlap_warnings(parsed.sources, results["suspicious"][0], "suspicious-text")

    certificate = words["certificate"] in lines[:3]
    ai_writing = None
    if "ai" in results:
        pieces = [piece for drawing in drawings for piece in _read_order(drawing.pieces)]
        segments = _ai_segments(drawings, pieces[body_at]) if body_at is not None else []
        ai_writing = AiWriting(overall_percent=results["ai"][0], segments=segments)
        if certificate:
            warnings.append(
                "This is a Compilatio analysis certificate, which has no copy of the document, "
                "so the passages flagged as AI cannot be read; the full analysis report has them."
            )
        elif results["ai"][0] > 0 and not segments:
            warnings.append(
                "The report gives an AI percentage, but no passage underlined in Compilatio's AI "
                "colour was found; the flagged passages could not be read."
            )
        elif segments:
            warnings.append(
                "The passages Compilatio attributes to AI were read from their underline in the "
                "PDF; check them against the report."
            )
        if details["included_in_suspicious"].get("ai") is False:
            warnings.append(
                "The report says its AI result is not included in its suspicious-text percentage."
            )
    else:
        warnings.append("The AI percentage could not be read.")

    months = words["months"]
    extensions: dict[str, Any] = {
        "layout": "magister_plus",
        "language": language,
        "document": "certificate" if certificate else "report",
        "source_groups": parsed.groups,
        "source_origins": parsed.origins,
        "semantic_sources": parsed.semantic,
        "mentioned_sources": parsed.mentioned,
        "deposited_on": day(after(head, words["deposited_on"]), months),
        "analysed_on": day(after(head, words["analysed_on"]), months),
        **details,
    }
    for key in ("suspicious", "quoted", "unrecognised_languages"):
        if key in results:
            extensions[f"{key}_percent"] = results[key][0]
            extensions[f"{key}_percent_is_upper_bound"] = results[key][1]
    return build_report(
        download,
        words["product"],
        submission(
            after(head, words["file_name"], stop=words["file_size"]),
            count(after(head, words["word_count"])),
            count(after(head, words["character_count"])),
        ),
        Similarity(overall_percent=overall, sources=parsed.sources),
        ai_writing,
        warnings,
        extensions,
    )
