import io
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fpdf import FPDF
from fpdf.enums import TextMode
from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.errors import DependencyError, PdfReadError

from draftwitness.core.documents import DocumentError
from draftwitness.core.documents import archive as archive_module
from draftwitness.modules.pre.inspect import (
    Finding,
    FindingKind,
    Inspection,
    Level,
    Location,
    inspect_bytes,
    inspect_file,
)
from draftwitness.modules.pre.inspect.common import Passages, qualified
from draftwitness.modules.pre.inspect.odt import duration_minutes
from draftwitness.modules.pre.inspect.pdf import _TextState

TODAY = date(2026, 10, 27)
CREATED = datetime(2026, 10, 27, tzinfo=UTC)
# Synthetic passwords for synthetic test PDFs.
USER_PASSWORD = "synthetic-user"  # noqa: S105
OWNER_PASSWORD = "synthetic-owner"  # noqa: S105
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
MC = 'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
PKG = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
CORE = (
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/'
    'core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:dcterms="http://purl.org/dc/terms/">'
    "<dc:title>Essay</dc:title><dc:creator>Student A</dc:creator>"
    "<cp:lastModifiedBy>Student A</cp:lastModifiedBy><cp:revision>7</cp:revision>"
    "<dc:description>   </dc:description></cp:coreProperties>"
)
APP = (
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
    'extended-properties"><Template>Normal.dotm</Template><TotalTime>95</TotalTime>'
    "<Application>Microsoft Office Word</Application>"
    "<HeadingPairs><vector/></HeadingPairs></Properties>"
)
CUSTOM = (
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"'
    ' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    '<property name="Course"><vt:lpwstr>HIS-101</vt:lpwstr></property></Properties>'
)
STYLES = (
    f"<w:styles {W}><w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val='24'/></w:rPr>"
    "</w:rPrDefault></w:docDefaults>"
    "<w:style w:type='paragraph' w:default='1' w:styleId='Normal'/>"
    "<w:style w:type='character' w:styleId='Secret'><w:rPr><w:vanish/></w:rPr></w:style>"
    "<w:style w:type='character' w:styleId='SecretChild'><w:basedOn w:val='Secret'/></w:style>"
    "<w:style w:type='paragraph' w:styleId='Ghost'><w:basedOn w:val='Ghost'/>"
    "<w:rPr><w:color w:val='FFFFFF'/></w:rPr></w:style>"
    "</w:styles>"
)


def _zip(members: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _docx(body: str, parts: dict[str, str | bytes] | None = None) -> bytes:
    members: dict[str, str | bytes] = {
        "word/document.xml": f"<w:document {W} {R} {MC}><w:body>{body}</w:body></w:document>"
    }
    members.update(parts or {})
    return _zip(members)


def _kinds(result: Inspection) -> dict[FindingKind, Finding]:
    return {f.kind: f for f in result.findings}


def _run(text: str, props: str = "", rsid: str = "") -> str:
    attr = f' w:rsidR="{rsid}"' if rsid else ""
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f"<w:r{attr}>{rpr}<w:t xml:space='preserve'>{text}</w:t></w:r>"


# --- text ---------------------------------------------------------------------------------


def test_text_file_lines_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "essay.txt"
    path.write_bytes("\ufeffTitle\r\nSecond\u200b line\n".encode())
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    result = inspect_file(path, today=TODAY)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert result.file.format == "text"
    assert result.file.size_bytes == len(before[0])
    assert len(result.file.sha256) == 64
    kinds = _kinds(result)
    assert set(kinds) == {FindingKind.BYTE_ORDER_MARK, FindingKind.FORMAT_CHARACTERS}
    finding = result.findings[0]
    assert finding.kind is FindingKind.FORMAT_CHARACTERS
    assert finding.occurrences[0].location == Location(line=2)
    assert result.metadata == []
    assert result.unidata_version


def test_text_file_must_be_utf8() -> None:
    with pytest.raises(DocumentError, match="not UTF-8"):
        inspect_bytes("café".encode("latin-1"), "essay.md", today=TODAY)


def test_unsupported_suffix() -> None:
    with pytest.raises(DocumentError, match="unsupported file type"):
        inspect_bytes(b"", "essay.rtf", today=TODAY)


def test_not_a_zip() -> None:
    with pytest.raises(DocumentError, match="ZIP"):
        inspect_bytes(b"plain", "essay.docx", today=TODAY)
    with pytest.raises(DocumentError, match="ZIP"):
        inspect_bytes(b"plain", "essay.odt", today=TODAY)


# --- DOCX ---------------------------------------------------------------------------------


def test_docx_minimal_reports_zero_rsids() -> None:
    result = inspect_bytes(_docx("<w:p>" + _run("Plain text.") + "</w:p>"), "a.docx", today=TODAY)
    assert result.file.format == "docx"
    rsids = _kinds(result)[FindingKind.RSIDS]
    assert rsids.level is Level.INFO
    assert rsids.details == {
        "in_settings": 0,
        "in_body_text": 0,
        "body_characters": 11,
        "characters_without_rsid": 11,
    }
    assert set(_kinds(result)) == {FindingKind.RSIDS}


def test_docx_missing_document_part() -> None:
    with pytest.raises(DocumentError, match=r"word/document\.xml"):
        inspect_bytes(_zip({"other.xml": "<a/>"}), "a.docx", today=TODAY)


def test_docx_properties_and_editing_time() -> None:
    data = _docx(
        "<w:p/>",
        {"docProps/core.xml": CORE, "docProps/app.xml": APP, "docProps/custom.xml": CUSTOM},
    )
    result = inspect_bytes(data, "a.docx", today=TODAY)
    fields = {(m.part, m.name): m.value for m in result.metadata}
    assert fields[("docProps/core.xml", "dc:creator")] == "Student A"
    assert fields[("docProps/core.xml", "cp:revision")] == "7"
    assert ("docProps/core.xml", "dc:description") not in fields
    assert fields[("docProps/app.xml", "app:TotalTime")] == "95"
    assert ("docProps/app.xml", "app:HeadingPairs") not in fields
    assert fields[("docProps/custom.xml", "Course")] == "HIS-101"
    editing = _kinds(result)[FindingKind.EDITING_TIME]
    assert editing.details == {"minutes": 95}


def test_docx_rsids() -> None:
    body = (
        '<w:p w:rsidR="00A1" w:rsidRDefault="00A1">'
        + _run("a" * 80)
        + _run("b" * 20, rsid="00B2")
        + "</w:p>"
    )
    settings = f"<w:settings {W}><w:rsids><w:rsidRoot w:val='00A1'/><w:rsid w:val='00A1'/>"
    settings += "<w:rsid w:val='00B2'/><w:rsid w:val='00C3'/></w:rsids></w:settings>"
    result = inspect_bytes(_docx(body, {"word/settings.xml": settings}), "a.docx", today=TODAY)
    rsids = _kinds(result)[FindingKind.RSIDS]
    assert rsids.count == 3
    assert rsids.details == {
        "in_settings": 3,
        "in_body_text": 2,
        "body_characters": 100,
        "largest_share": 80,
    }


def test_docx_tracked_changes_and_comments() -> None:
    body = (
        "<w:p>"
        '<w:ins w:id="1" w:author="Student A" w:date="2026-10-01T10:00:00Z">'
        + _run("new")
        + "</w:ins>"
        '<w:del w:id="2" w:author="Tutor B" w:date="2026-10-03T10:00:00Z">'
        "<w:r><w:delText>old\u200b text</w:delText></w:r></w:del>"
        '<w:moveFrom w:id="3" w:author="">' + _run("moved") + "</w:moveFrom>"
        '<w:r><w:rPr><w:b/><w:rPrChange w:id="4" w:author="Student A"/></w:rPr>'
        "<w:t>bold</w:t></w:r></w:p>"
    )
    comments = (
        f"<w:comments {W}><w:comment w:id='0' w:author='Tutor B'><w:p>"
        + _run("Check this")
        + "</w:p></w:comment><w:comment w:id='1'><w:p/></w:comment></w:comments>"
    )
    result = inspect_bytes(_docx(body, {"word/comments.xml": comments}), "a.docx", today=TODAY)
    kinds = _kinds(result)
    changes = kinds[FindingKind.TRACKED_CHANGES]
    assert changes.level is Level.REVIEW
    assert changes.count == 4
    assert changes.details == {
        "insertions": 1,
        "deletions": 1,
        "moves": 1,
        "formatting": 1,
        "authors": "Student A, Tutor B",
        "first_date": "2026-10-01T10:00:00Z",
        "last_date": "2026-10-03T10:00:00Z",
    }
    assert kinds[FindingKind.COMMENTS].count == 2
    assert kinds[FindingKind.COMMENTS].details == {"authors": "Tutor B"}
    # Deleted text is still in the file, so its characters are inspected too.
    assert FindingKind.FORMAT_CHARACTERS in kinds
    comment_segments = [o.location.part for o in kinds[FindingKind.FORMAT_CHARACTERS].occurrences]
    assert comment_segments == ["word/document.xml"]


def test_docx_hidden_white_and_tiny_text() -> None:
    body = (
        "<w:p>"
        + _run("visible ")
        + _run("hidden direct", "<w:vanish/>")
        + _run("not hidden", "<w:vanish w:val='false'/>")
        + _run("hidden by style", "<w:rStyle w:val='SecretChild'/>")
        + _run("white", "<w:color w:val='FFFFFF'/>")
        + _run("white on black", "<w:color w:val='FFFFFF'/><w:shd w:val='clear' w:fill='000000'/>")
        + _run("white highlighted", "<w:color w:val='FFFFFF'/><w:highlight w:val='black'/>")
        + _run("white on white", "<w:color w:val='FFFFFF'/><w:highlight w:val='white'/>")
        + _run("tiny", "<w:sz w:val='2'/>")
        + _run("   ", "<w:vanish/>")
        + "</w:p>"
        "<w:p><w:pPr><w:pStyle w:val='Ghost'/></w:pPr>" + _run("ghost paragraph") + "</w:p>"
    )
    result = inspect_bytes(_docx(body, {"word/styles.xml": STYLES}), "a.docx", today=TODAY)
    kinds = _kinds(result)
    hidden = kinds[FindingKind.HIDDEN_TEXT]
    assert [o.text for o in hidden.occurrences] == ["hidden direct", "hidden by style"]
    assert hidden.details == {"characters": 28}
    white = kinds[FindingKind.WHITE_TEXT]
    assert [o.text for o in white.occurrences] == [
        "white",
        "white on white",
        "ghost paragraph",
    ]
    assert white.occurrences[2].location == Location(part="word/document.xml", paragraph=2)
    assert [o.text for o in kinds[FindingKind.TINY_TEXT].occurrences] == ["tiny"]


def test_docx_text_parts_nested_paragraphs_and_symbols() -> None:
    body = (
        "<w:p>"
        + _run("Anchor")
        + "<w:r><mc:AlternateContent><mc:Choice><w:drawing><w:txbxContent><w:p>"
        + _run("In\u200b box")
        + "</w:p></w:txbxContent></w:drawing></mc:Choice><mc:Fallback><w:p>"
        + _run("In\u200b box")
        + "</w:p></mc:Fallback></mc:AlternateContent></w:r>"
        "<w:r><w:tab/><w:sym w:font='Wingdings' w:char='F04A'/><w:sym w:char='zz'/></w:r></w:p>"
    )
    header = f"<w:hdr {W}><w:p>" + _run("Header\u00a0text") + "</w:p></w:hdr>"
    data = _docx(body, {"word/header1.xml": header, "word/footnotes.xml": f"<w:footnotes {W}/>"})
    result = inspect_bytes(data, "a.docx", today=TODAY)
    kinds = _kinds(result)
    occurrences = kinds[FindingKind.FORMAT_CHARACTERS].occurrences
    assert [o.location for o in occurrences] == [Location(part="word/document.xml", paragraph=2)]
    assert kinds[FindingKind.PRIVATE_USE].count == 1
    nbsp = kinds[FindingKind.NO_BREAK_SPACES].occurrences[0]
    assert nbsp.location == Location(part="word/header1.xml", paragraph=1)


def test_docx_fields() -> None:
    body = (
        "<w:p><w:fldSimple w:instr=' PAGE \\* MERGEFORMAT '><w:r><w:t>1</w:t></w:r></w:fldSimple>"
        "<w:r><w:fldChar w:fldCharType='begin'/></w:r>"
        "<w:r><w:instrText> ADDIN ZOTERO_ITEM CSL_CITATION</w:instrText></w:r>"
        '<w:r><w:instrText> {"citationID":"x"}</w:instrText></w:r>'
        "<w:r><w:fldChar w:fldCharType='separate'/></w:r>" + _run("(Smith, 2020)") + ""
        "<w:r><w:fldChar w:fldCharType='end'/></w:r>"
        "<w:r><w:fldChar w:fldCharType='begin'/></w:r><w:r><w:instrText>HYPERLINK x</w:instrText>"
        "</w:r><w:r><w:fldChar w:fldCharType='end'/></w:r>"
        "<w:r><w:fldChar w:fldCharType='begin'/></w:r><w:r><w:fldChar w:fldCharType='end'/></w:r>"
        "<w:fldSimple w:instr='  '/><w:r><w:fldChar w:fldCharType='end'/></w:r>"
        "</w:p>"
    )
    result = inspect_bytes(_docx(body), "a.docx", today=TODAY)
    fields = _kinds(result)[FindingKind.FIELDS]
    assert fields.details == {"ADDIN ZOTERO_ITEM": 1, "HYPERLINK": 1, "PAGE": 1}
    assert fields.count == 3


def test_docx_packages_alt_chunks_macros_and_template() -> None:
    rels = (
        f"<Relationships {PKG}><Relationship Id='rId9' Type='x' Target='afchunk.htm'/>"
        "</Relationships>"
    )
    settings = f"<w:settings {W} {R}><w:attachedTemplate r:id='rId1'/></w:settings>"
    settings_rels = (
        f"<Relationships {PKG}><Relationship Id='rId1' Type='t' "
        "Target='file:///C:/Users/someone/Templates/Thesis.dotx' TargetMode='External'/>"
        "</Relationships>"
    )
    data = _docx(
        "<w:altChunk r:id='rId9'/><w:p/>",
        {
            "word/_rels/document.xml.rels": rels,
            "word/settings.xml": settings,
            "word/_rels/settings.xml.rels": settings_rels,
            "word/embeddings/oleObject1.bin": b"\x00",
            "word/vbaProject.bin": b"\x00",
        },
    )
    result = inspect_bytes(data, "a.docm", today=TODAY)
    kinds = _kinds(result)
    assert kinds[FindingKind.ALT_CHUNKS].details == {"parts": "afchunk.htm"}
    assert kinds[FindingKind.EMBEDDED_OBJECTS].details == {
        "parts": "word/embeddings/oleObject1.bin"
    }
    assert kinds[FindingKind.MACROS].level is Level.REVIEW
    assert kinds[FindingKind.ATTACHED_TEMPLATE].details == {
        "target": "file:///C:/Users/someone/Templates/Thesis.dotx"
    }


def test_docx_template_without_relationship() -> None:
    settings = f"<w:settings {W} {R}><w:attachedTemplate r:id='rId1'/></w:settings>"
    result = inspect_bytes(_docx("<w:p/>", {"word/settings.xml": settings}), "a.docx", today=TODAY)
    assert _kinds(result)[FindingKind.ATTACHED_TEMPLATE].details == {}


def test_docx_xml_bomb_is_refused() -> None:
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;">]><w:document><w:body>&lol2;</w:body></w:document>'
    )
    with pytest.raises(DocumentError):
        inspect_bytes(_zip({"word/document.xml": bomb}), "a.docx", today=TODAY)


def test_docx_oversized_member_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive_module, "MAX_MEMBER_BYTES", 10)
    with pytest.raises(DocumentError, match="larger than"):
        inspect_bytes(_docx("<w:p/>"), "a.docx", today=TODAY)


# --- ODT ----------------------------------------------------------------------------------

ODF_NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink"'
)
ODF_STYLES = (
    "<office:automatic-styles>"
    '<style:style style:name="H"><style:text-properties text:display="none"/></style:style>'
    '<style:style style:name="Wh"><style:text-properties fo:color="#FFFFFF"/></style:style>'
    '<style:style style:name="WhBg" style:parent-style-name="Wh">'
    '<style:text-properties fo:background-color="#000000"/></style:style>'
    '<style:style style:name="T"><style:text-properties fo:font-size="1pt"/></style:style>'
    '<style:style style:name="Big"><style:text-properties fo:font-size="12pt"/></style:style>'
    '<style:style style:name="Loop" style:parent-style-name="Loop"/>'
    "</office:automatic-styles>"
)


def _odt(body: str, *, meta: str | None = None, **extra: str | bytes) -> bytes:
    content = (
        f"<office:document-content {ODF_NS}>{ODF_STYLES}<office:body><office:text>{body}"
        "</office:text></office:body></office:document-content>"
    )
    members: dict[str, str | bytes] = {"mimetype": "application/vnd.oasis.opendocument.text"}
    members["content.xml"] = content
    members["styles.xml"] = (
        f"<office:document-styles {ODF_NS}><office:master-styles><style:master-page>"
        "<style:header><text:p>Header\u200b</text:p></style:header>"
        "</style:master-page></office:master-styles></office:document-styles>"
    )
    if meta is not None:
        members["meta.xml"] = (
            f"<office:document-meta {ODF_NS}><office:meta>{meta}</office:meta>"
            "</office:document-meta>"
        )
    members.update(extra)
    return _zip(members)


def test_odt_text_hidden_white_tiny_and_notes() -> None:
    body = (
        "<text:p>Plain<text:s text:c='2'/>text<text:tab/>tab<text:line-break/>"
        "<text:span text:style-name='H'>hidden span <text:span text:style-name='T'>x</text:span>"
        "</text:span>"
        "<text:span text:style-name='Wh'>white</text:span>"
        "<text:span text:style-name='WhBg'>white on black</text:span>"
        "<text:span text:style-name='T'>tiny</text:span>"
        "<text:span text:style-name='Big'>big</text:span>"
        "<text:span text:style-name='Loop'>loop</text:span>"
        "<text:hidden-text text:string-value='conditional' text:condition='ooow:1'/>"
        "<text:note><text:note-citation>1</text:note-citation><text:note-body>"
        "<text:p>Note\u00a0text</text:p></text:note-body></text:note>"
        "<office:annotation><dc:creator>Tutor B</dc:creator><text:p>Comment</text:p>"
        "</office:annotation><text:soft-page-break/></text:p>"
        "<text:section text:name='S' text:display='none'><text:p>section text</text:p>"
        "</text:section>"
    )
    result = inspect_bytes(_odt(body), "a.odt", today=TODAY)
    assert result.file.format == "odt"
    kinds = _kinds(result)
    hidden = [o.text for o in kinds[FindingKind.HIDDEN_TEXT].occurrences]
    assert hidden == ["hidden span x", "conditional", "section text"]
    white = [o.text for o in kinds[FindingKind.WHITE_TEXT].occurrences]
    assert white == ["white"]
    tiny = [o.text for o in kinds[FindingKind.TINY_TEXT].occurrences]
    assert tiny == ["tiny"]
    assert kinds[FindingKind.COMMENTS].details == {"authors": "Tutor B"}
    nbsp = kinds[FindingKind.NO_BREAK_SPACES].occurrences[0]
    assert nbsp.location.part == "content.xml"
    header = kinds[FindingKind.FORMAT_CHARACTERS].occurrences[0]
    assert header.location == Location(part="styles.xml", paragraph=1)


def test_odt_meta_changes_and_packages() -> None:
    meta = (
        "<meta:generator>LibreOffice/24.2</meta:generator><dc:creator>Student A</dc:creator>"
        "<meta:editing-cycles>12</meta:editing-cycles>"
        "<meta:editing-duration>PT2H5M30S</meta:editing-duration>"
        "<meta:document-statistic meta:word-count='1200' meta:page-count='4'/>"
        "<meta:user-defined meta:name='Course'>HIS-101</meta:user-defined>"
        "<meta:template xlink:href='../Templates/thesis.ott' xlink:title='Thesis'/>"
    )
    changes = (
        "<text:tracked-changes><text:changed-region text:id='c1'><text:deletion>"
        "<office:change-info><dc:creator>Student A</dc:creator>"
        "<dc:date>2026-10-02T09:00:00</dc:date></office:change-info>"
        "<text:p>deleted</text:p></text:deletion></text:changed-region>"
        "<text:changed-region text:id='c2'><text:insertion><office:change-info>"
        "<dc:creator>Student A</dc:creator></office:change-info></text:insertion>"
        "<text:format-change/><text:unknown/></text:changed-region></text:tracked-changes>"
    )
    data = _odt(
        changes + "<text:p>Body</text:p>",
        meta=meta,
        **{
            "Object 1/content.xml": "<x/>",
            "Basic/Standard/Module1.xml": "<x/>",
            "Basic/script-lc.xml": "<x/>",
        },
    )
    result = inspect_bytes(data, "a.odt", today=TODAY)
    fields = {m.name: m.value for m in result.metadata}
    assert fields["meta:generator"] == "LibreOffice/24.2"
    assert fields["meta:document-statistic"] == "word-count=1200, page-count=4"
    assert fields["Course"] == "HIS-101"
    assert "meta:user-defined" not in fields
    assert fields["meta:template"] == "href=../Templates/thesis.ott, title=Thesis"
    kinds = _kinds(result)
    assert kinds[FindingKind.EDITING_TIME].details == {
        "minutes": 125,
        "duration": "PT2H5M30S",
    }
    assert kinds[FindingKind.EDITING_CYCLES].count == 12
    assert kinds[FindingKind.TRACKED_CHANGES].details == {
        "deletions": 1,
        "insertions": 1,
        "formatting": 1,
        "authors": "Student A",
        "first_date": "2026-10-02T09:00:00",
        "last_date": "2026-10-02T09:00:00",
    }
    assert kinds[FindingKind.EMBEDDED_OBJECTS].details == {"parts": "Object 1"}
    assert kinds[FindingKind.MACROS].details == {"parts": "Basic/Standard/Module1.xml"}


def test_odt_meta_without_office_meta_and_bad_values() -> None:
    data = _odt("<text:p>x</text:p>", meta="<meta:editing-duration>soon</meta:editing-duration>")
    result = inspect_bytes(data, "a.odt", today=TODAY)
    assert FindingKind.EDITING_TIME not in _kinds(result)
    empty = _zip(
        {
            "content.xml": f"<office:document-content {ODF_NS}/>",
            "meta.xml": f"<office:document-meta {ODF_NS}/>",
        }
    )
    assert inspect_bytes(empty, "a.odt", today=TODAY).metadata == []


def test_odt_missing_content() -> None:
    with pytest.raises(DocumentError, match=r"content\.xml"):
        inspect_bytes(_zip({"styles.xml": "<a/>"}), "a.odt", today=TODAY)


@pytest.mark.parametrize(
    ("value", "minutes"),
    [("PT1H2M3S", 62), ("P1DT0H", 1440), ("PT90.5S", 1), ("PT", None), ("P", None), ("x", None)],
)
def test_duration_minutes(value: str, minutes: int | None) -> None:
    assert duration_minutes(value) == minutes


# --- PDF ----------------------------------------------------------------------------------


def _pdf(*, invisible: bool = False, white: bool = False, text: str = "Visible text") -> bytes:
    pdf = FPDF()
    pdf.set_creation_date(CREATED)
    pdf.set_author("Student A")
    pdf.set_producer("Synthetic producer")
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(text=text)
    pdf.ln()
    if white:
        pdf.set_text_color(255, 255, 255)
        pdf.cell(text="White words")
        pdf.set_text_color(0, 0, 0)
        pdf.ln()
    if invisible:
        # The render mode is part of the text state and persists across text objects, so
        # it must come last: fpdf2 does not reset it in the content stream.
        pdf.text_mode = TextMode.INVISIBLE
        pdf.cell(text="Hidden layer")
        pdf.ln()
    return bytes(pdf.output())


def test_pdf_metadata_and_clean_text() -> None:
    result = inspect_bytes(_pdf(), "a.pdf", today=TODAY)
    assert result.file.format == "pdf"
    fields = {(m.part, m.name): m.value for m in result.metadata}
    assert fields[("Info", "Author")] == "Student A"
    assert fields[("Info", "Producer")] == "Synthetic producer"
    assert result.findings == []


def test_pdf_invisible_and_white_text() -> None:
    result = inspect_bytes(_pdf(invisible=True, white=True), "a.pdf", today=TODAY)
    kinds = _kinds(result)
    invisible = kinds[FindingKind.INVISIBLE_TEXT]
    assert [o.text for o in invisible.occurrences] == ["Hidden layer"]
    assert invisible.occurrences[0].location == Location(page=1)
    white = kinds[FindingKind.WHITE_TEXT]
    assert [o.text for o in white.occurrences] == ["White words"]


def test_pdf_characters_are_scanned() -> None:
    result = inspect_bytes(_pdf(text="Soft\u00adhyphen"), "a.pdf", today=TODAY)
    assert FindingKind.SOFT_HYPHENS in _kinds(result)


def _rewrite(
    data: bytes, *, attachment: bytes | None = None, user_password: str | None = None
) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    if attachment is not None:
        writer.add_attachment("notes.txt", attachment)
    if user_password is not None:
        writer.encrypt(user_password, OWNER_PASSWORD, algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_incremental_update() -> None:
    original = _pdf()
    writer = PdfWriter(io.BytesIO(original), incremental=True)
    writer.add_metadata({"/Title": "Edited"})
    buffer = io.BytesIO()
    writer.write(buffer)
    result = inspect_bytes(buffer.getvalue(), "a.pdf", today=TODAY)
    finding = _kinds(result)[FindingKind.INCREMENTAL_UPDATES]
    assert finding.count == 1
    assert finding.details == {"eof_markers": 2, "linearized": "no"}


def test_pdf_linearized_marker_is_not_an_update() -> None:
    data = _pdf().replace(b"%PDF-1.3\n", b"%PDF-1.3\n% /Linearized\n%%EOF\n", 1)
    assert FindingKind.INCREMENTAL_UPDATES not in _kinds(inspect_bytes(data, "a.pdf", today=TODAY))


def test_pdf_attachments() -> None:
    data = _rewrite(_pdf(), attachment=b"draft")
    finding = _kinds(inspect_bytes(data, "a.pdf", today=TODAY))[FindingKind.ATTACHMENTS]
    assert finding.details == {"names": "notes.txt"}


def test_pdf_encrypted_with_empty_user_password_is_inspected() -> None:
    data = _rewrite(_pdf(), user_password="")
    result = inspect_bytes(data, "a.pdf", today=TODAY)
    encrypted = _kinds(result)[FindingKind.ENCRYPTED]
    assert encrypted.details == {"opened_without_password": "yes"}
    assert any(m.name == "Author" for m in result.metadata)


def test_pdf_locked() -> None:
    data = _rewrite(_pdf(), user_password=USER_PASSWORD)
    result = inspect_bytes(data, "a.pdf", today=TODAY)
    assert _kinds(result)[FindingKind.ENCRYPTED].details == {"opened_without_password": "no"}
    assert result.notes == ["pdf_locked"]
    assert result.metadata == []


XMP = """<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
 xmlns:stEvt="http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"
 xmp:CreatorTool="Synthetic Writer 1.0" xmp:Label="  ">
<dc:creator><rdf:Seq><rdf:li>Student A</rdf:li></rdf:Seq></dc:creator>
<xmpMM:History><rdf:Seq><rdf:li stEvt:action="created"/><rdf:li stEvt:action="saved"/>
</rdf:Seq></xmpMM:History><xmpMM:DocumentID>uuid:1234</xmpMM:DocumentID><xmp:Empty/>
</rdf:Description></rdf:RDF></x:xmpmeta>"""


def _with_xmp(xmp: str) -> bytes:
    pdf = FPDF()
    pdf.set_creation_date(CREATED)
    pdf.set_xmp_metadata(xmp)
    pdf.add_page()
    return bytes(pdf.output())


def test_pdf_xmp() -> None:
    result = inspect_bytes(_with_xmp(XMP), "a.pdf", today=TODAY)
    fields = {m.name: m.value for m in result.metadata if m.part == "XMP"}
    assert fields == {
        "xmp:CreatorTool": "Synthetic Writer 1.0",
        "dc:creator": "Student A",
        "xmpMM:History": "2 entries",
        "xmpMM:DocumentID": "uuid:1234",
    }


def test_pdf_xmp_unreadable_and_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    result = inspect_bytes(_with_xmp("<not xml"), "a.pdf", today=TODAY)
    assert result.notes == ["xmp_unreadable"]
    monkeypatch.setattr("draftwitness.modules.pre.inspect.pdf.MAX_MEMBER_BYTES", 5)
    result = inspect_bytes(_with_xmp(XMP), "a.pdf", today=TODAY)
    assert result.notes == ["xmp_too_large"]


def test_pdf_unreadable() -> None:
    with pytest.raises(DocumentError, match="cannot read PDF"):
        inspect_bytes(b"%PDF-1.4 garbage", "a.pdf", today=TODAY)


def test_pdf_text_state_follows_graphics_state() -> None:

    invisible, white = Passages(), Passages()
    state = _TextState(Location(page=1), invisible, white)
    steps: list[tuple[bytes, list[Any]]] = [
        (b"q", []),
        (b"Tr", [3]),
        (b"Tj", [b"a"]),
        (b"Q", []),
        (b"Q", []),  # unbalanced restore is ignored
        (b"Tr", ["bad"]),
        (b"k", [0, 0, 0, 0]),
        (b"TJ", [[b"b"]]),
    ]
    texts = iter(["hidden", "white", "plain", "  "])
    for operator, operands in steps:
        state.before(operator, operands, None, None)
        if operator in {b"Tj", b"TJ"}:
            state.text(next(texts), None, None, None, None)
    for operator, operands in [(b"cs", [b"/DeviceRGB"]), (b"Tj", [b"c"])]:
        state.before(operator, operands, None, None)
    state.text(next(texts), None, None, None, None)
    state.text(next(texts), None, None, None, None)
    state.before(b"scn", ["/P0"], None, None)
    assert state.fill_white is False
    state.before(b"sc", [1, 1], None, None)
    assert state.fill_white is False
    assert [o.text for o in invisible.occurrences] == ["hidden"]
    assert [o.text for o in white.occurrences] == ["white"]


def test_pdf_without_info_dictionary() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    result = inspect_bytes(buffer.getvalue(), "a.pdf", today=TODAY)
    assert all(m.part != "Info" or m.name == "Producer" for m in result.metadata)


def test_pdf_reader_failures(monkeypatch: pytest.MonkeyPatch) -> None:

    def broken(*_args: object, **_kwargs: object) -> object:
        raise PdfReadError("broken")

    def missing(*_args: object, **_kwargs: object) -> object:
        raise DependencyError("cryptography is required")

    monkeypatch.setattr(PdfReader, "attachments", property(broken))
    result = inspect_bytes(_pdf(), "a.pdf", today=TODAY)
    assert result.notes == ["attachments_unreadable"]

    locked = _rewrite(_pdf(), user_password="")
    monkeypatch.setattr(PdfReader, "decrypt", missing)
    assert inspect_bytes(locked, "a.pdf", today=TODAY).notes == ["pdf_locked"]

    monkeypatch.setattr(PageObject, "extract_text", broken)
    with pytest.raises(DocumentError, match="cannot read PDF"):
        inspect_bytes(_pdf(), "a.pdf", today=TODAY)


def test_odt_text_box_paragraphs_are_segments() -> None:
    body = (
        "<text:p>Anchor<draw:frame xmlns:draw='urn:oasis:names:tc:opendocument:xmlns:drawing:1.0'>"
        "<draw:text-box><text:p>Box\u200b</text:p></draw:text-box></draw:frame></text:p>"
    )
    result = inspect_bytes(_odt(body), "a.odt", today=TODAY)
    occurrence = _kinds(result)[FindingKind.FORMAT_CHARACTERS].occurrences[0]
    assert occurrence.location == Location(part="content.xml", paragraph=2)


def test_qualified_names() -> None:

    assert qualified("plain") == "plain"
    assert qualified("{urn:unknown}name") == "name"
    assert qualified("{http://purl.org/dc/elements/1.1/}creator") == "dc:creator"
