import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from descargo.core.documents import (
    DocumentError,
    archive,
    count_words,
    extract_text,
    text_document,
)

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
MC = 'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'


def _zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def _docx(path: Path, body: str, footnotes: str | None = None) -> Path:
    members = {"word/document.xml": f"<w:document {W} {MC}><w:body>{body}</w:body></w:document>"}
    if footnotes is not None:
        members["word/footnotes.xml"] = f"<w:footnotes {W}>{footnotes}</w:footnotes>"
    return _zip(path, members)


def test_count_words() -> None:
    assert count_words("Rock-solid evidence, isn't it? 2026 — yes.") == 6
    assert count_words("") == 0


def test_plain_text_paragraphs_and_block_quotes() -> None:
    doc = text_document("First line\nsame paragraph.\n\n> Quoted\n> text.\n\nLast.")
    assert [doc.text[p.start : p.end] for p in doc.paragraphs] == [
        "First line\nsame paragraph.",
        "Quoted\ntext.",
        "Last.",
    ]
    assert [p.quote for p in doc.paragraphs] == [False, True, False]
    assert doc.body_end == len(doc.text)
    assert doc.word_count == 7
    assert doc.paragraph_at(doc.paragraphs[1].start + 2) == doc.paragraphs[1]
    assert doc.paragraph_at(-1) is None


def test_extract_markdown_file(tmp_path: Path) -> None:
    path = tmp_path / "essay.md"
    path.write_text("﻿Title\n\nBody.", encoding="utf-8")
    doc = extract_text(path)
    assert doc.text == "Title\n\nBody."
    assert doc.source_format == "text"


def test_docx_text_quotes_notes_and_marks(tmp_path: Path) -> None:
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Title</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>Plain </w:t></w:r><w:r><w:t>text</w:t><w:tab/><w:t>tab</w:t>"
        "<w:br/><w:t>break</w:t></w:r>"
        '<w:r><w:footnoteReference w:id="1"/></w:r>'
        "<w:del><w:r><w:delText>deleted</w:delText></w:r></w:del></w:p>"
        '<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>A block quote.</w:t></w:r>'
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>'
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>th</w:t></w:r></w:p>'
        "<w:p><w:r><mc:AlternateContent><mc:Choice><w:txbxContent>"
        "<w:p><w:r><w:t>In a text box</w:t></w:r></w:p></w:txbxContent></mc:Choice>"
        "<mc:Fallback><w:p><w:r><w:t>In a text box</w:t></w:r></w:p></mc:Fallback>"
        "</mc:AlternateContent></w:r><w:r><w:t>Anchor</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    )
    footnotes = (
        '<w:footnote w:type="separator" w:id="0"><w:p><w:r><w:t>---</w:t></w:r></w:p></w:footnote>'
        '<w:footnote w:id="1"><w:p><w:r><w:t>Smith, 2020.</w:t></w:r></w:p></w:footnote>'
    )
    doc = extract_text(_docx(tmp_path / "work.docx", body, footnotes))
    paragraphs = [doc.text[p.start : p.end] for p in doc.paragraphs]
    assert paragraphs == [
        "Title",
        "Plain text\ttab\nbreak",
        "A block quote.2th",
        "Anchor",
        "In a text box",
        "Cell",
        "Smith, 2020.",
    ]
    assert "deleted" not in doc.text
    assert doc.text.count("In a text box") == 1
    assert [p.quote for p in doc.paragraphs][:3] == [False, False, True]
    assert doc.paragraphs[-1].note
    assert doc.body_end == doc.paragraphs[-2].end
    footnote_mark = doc.paragraphs[1].end
    superscript_mark = doc.text.index("2th")
    assert doc.citation_marks == (footnote_mark, superscript_mark)
    assert doc.source_format == "docx"


def _odt(path: Path, body: str, automatic_styles: str = "", styles: str | None = None) -> Path:
    ns = (
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"'
    )
    content = (
        f"<office:document-content {ns}><office:automatic-styles>{automatic_styles}"
        f"</office:automatic-styles><office:body><office:text>{body}</office:text>"
        "</office:body></office:document-content>"
    )
    members = {"mimetype": "application/vnd.oasis.opendocument.text", "content.xml": content}
    if styles is not None:
        members["styles.xml"] = (
            f"<office:document-styles {ns}><office:styles>{styles}</office:styles>"
            "</office:document-styles>"
        )
    return _zip(path, members)


def test_odt_text_quotes_notes_and_marks(tmp_path: Path) -> None:
    automatic = (
        '<style:style style:name="P1" style:parent-style-name="Quotations"/>'
        '<style:style style:name="T1"><style:text-properties style:text-position="super 58%"/>'
        "</style:style>"
    )
    body = (
        "<text:h>Title</text:h>"
        "<text:tracked-changes><text:changed-region><text:p>gone</text:p>"
        "</text:changed-region></text:tracked-changes>"
        '<text:p>Two<text:s text:c="2"/>spaces<text:tab/>tab<text:line-break/>line'
        "<text:note><text:note-citation>1</text:note-citation><text:note-body>"
        "<text:p>Smith, 2020.</text:p></text:note-body></text:note>"
        "<office:annotation><text:p>comment</text:p></office:annotation> end</text:p>"
        '<text:p text:style-name="P1">Quoted <text:span text:style-name="T1">3</text:span></text:p>'
        '<text:p text:style-name="Cita">Spanish quote style</text:p>'
        "<text:list><text:list-item><text:p>Item</text:p></text:list-item></text:list>"
    )
    styles = '<style:style style:name="Cita"/>'
    doc = extract_text(_odt(tmp_path / "work.odt", body, automatic, styles))
    paragraphs = [doc.text[p.start : p.end] for p in doc.paragraphs]
    assert paragraphs == [
        "Title",
        "Two  spaces\ttab\nline end",
        "Quoted 3",
        "Spanish quote style",
        "Item",
        "Smith, 2020.",
    ]
    assert "gone" not in doc.text
    assert "comment" not in doc.text
    assert [p.quote for p in doc.paragraphs] == [False, False, True, True, False, False]
    assert doc.paragraphs[-1].note
    assert doc.citation_marks == (doc.text.index(" end"), doc.text.index("3"))
    assert doc.source_format == "odt"


def _pdf(path: Path, lines: list[str]) -> Path:
    pdf = FPDF()
    pdf.set_creation_date(datetime(2026, 10, 27, tzinfo=UTC))
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    for line in lines:
        pdf.cell(0, 10, line, new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    pdf.cell(0, 10, "Second page.")
    path.write_bytes(bytes(pdf.output()))
    return path


def test_pdf_pages_become_paragraphs(tmp_path: Path) -> None:
    doc = extract_text(_pdf(tmp_path / "work.pdf", ["SYNTHETIC title", "Body text here."]))
    assert "Body text here." in doc.text
    assert doc.text.endswith("Second page.")
    assert len(doc.paragraphs) >= 2
    assert doc.source_format == "pdf"


def test_encrypted_pdf_is_refused(tmp_path: Path) -> None:
    source = _pdf(tmp_path / "plain.pdf", ["Secret"])
    writer = PdfWriter(clone_from=PdfReader(source))
    writer.encrypt("pw", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    path = tmp_path / "locked.pdf"
    path.write_bytes(buffer.getvalue())
    with pytest.raises(DocumentError, match="encrypted"):
        extract_text(path)


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("notes.rtf", b"{\\rtf1}", "unsupported document type"),
        ("broken.docx", b"not a zip", "File is not a zip file"),
        ("broken.pdf", b"%PDF-1.4 nothing else", "cannot read PDF"),
        ("bad.txt", b"\xff\xfe\xfa", "codec"),
    ],
)
def test_unreadable_files(tmp_path: Path, name: str, content: bytes, message: str) -> None:
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(DocumentError, match=message):
        extract_text(path)


def test_missing_main_part(tmp_path: Path) -> None:
    with pytest.raises(DocumentError, match=r"word/document\.xml is missing"):
        extract_text(_zip(tmp_path / "empty.docx", {"other.xml": "<a/>"}))
    with pytest.raises(DocumentError, match=r"content\.xml is missing"):
        extract_text(_zip(tmp_path / "empty.odt", {"other.xml": "<a/>"}))


def test_malformed_xml(tmp_path: Path) -> None:
    with pytest.raises(DocumentError, match=r"word/document\.xml"):
        extract_text(_zip(tmp_path / "bad.docx", {"word/document.xml": "<w:document"}))


def test_entity_expansion_is_refused(tmp_path: Path) -> None:
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        f"<w:document {W}><w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>"
    )
    with pytest.raises(DocumentError, match="EntitiesForbidden"):
        extract_text(_zip(tmp_path / "bomb.docx", {"word/document.xml": bomb}))


def test_oversized_member_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive, "MAX_MEMBER_BYTES", 10)
    path = _docx(tmp_path / "big.docx", "<w:p><w:r><w:t>Long enough text</w:t></w:r></w:p>")
    with pytest.raises(DocumentError, match="larger than"):
        extract_text(path)


def test_extraction_does_not_modify_the_file(tmp_path: Path) -> None:
    path = _docx(tmp_path / "work.docx", "<w:p><w:r><w:t>Unchanged</w:t></w:r></w:p>")
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    extract_text(path)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
