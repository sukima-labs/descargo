# Pre-submission inspection

`draftwitness inspect` lists what a file contains besides its visible text: invisible or
unusual characters, metadata, tracked changes, comments, hidden text and other content that
a reader or a tool may notice. It explains what each item usually means and what it does
not show. The design is in [ADR 006](adr/006-pre-submission-inspector.md).

It **reports and never changes your file**. It does not tell you what to change, gives no
score and no pass/fail, and exits with status 0 whenever it could read the file. If you edit
the file with your own tools, keep a copy of the original.

**Not legal advice.**

```bash
uv run draftwitness inspect my-essay.docx
uv run draftwitness --lang es inspect my-essay.odt --format pdf --out inspection.pdf
```

| Option | What it does |
|---|---|
| `--format md\|json\|pdf` | Output format (Markdown by default). |
| `--out FILE` | Write to a file instead of the terminal (required for PDF). |
| `--language en\|es` | Report language; defaults to the interface language. |
| `--date YYYY-MM-DD` | Date printed on the report; defaults to today. |
| `--force` | Overwrite an existing output file. |

Supported files: `.docx` (and `.docm`), `.odt`, `.pdf`, and UTF-8 `.txt` or `.md`.

## Levels

- **Worth reviewing**: a reader or a tool is likely to notice it. It does not mean anything
  is wrong.
- **For information**: common and usually innocent.

## What is checked

### Characters (every format)

| Finding | Level | Notes |
|---|---|---|
| Zero-width and other invisible format characters | review | U+200B, U+2060, U+FEFF inside text, invisible operators… |
| Zero-width joiners and non-joiners | info | Normal in Persian, Arabic, Indic scripts and emoji |
| Soft hyphens | info | Inserted by hyphenation |
| Text-direction marks and controls | info | Normal in right-to-left text |
| Text-direction overrides (U+202D, U+202E) | review | |
| Unbalanced text-direction controls | review | Checked per paragraph ("Trojan Source", CVE-2021-42574) |
| Tag characters (U+E0000–E007F) | review | The ASCII text they spell is shown |
| Emoji flags built from tag characters | info | England, Scotland, Wales… |
| Variation selectors | info | A single one after a character |
| Data hidden in variation selectors | review | Runs of selectors, decoded to bytes (and to text when readable) |
| Content credentials (C2PA manifest) | review | The C2PA 2.4 text wrapper: presence and size only |
| Control characters | review | Other than tab and line breaks |
| Private-use characters | info | Symbol fonts such as Wingdings |
| Unassigned code points | review | Depends on the Unicode version, which the report records |
| Unusual spaces | review | En, em, thin, ideographic… |
| Non-breaking spaces | info | U+00A0 and U+202F |
| Characters that look blank | review | Hangul fillers, blank Braille pattern |
| Unicode line and paragraph separators | info | |
| Words mixing alphabets | review | Latin with Cyrillic, or with Greek letters that look Latin. Other Greek letters (μm, β-cells) are not reported |
| Byte-order mark at the start of a text file | info | |

In DOCX files, characters are checked in the body, headers, footers, footnotes, endnotes
and comments, including deleted text that tracked changes keep. In ODT files they are
checked in `content.xml` and `styles.xml` (headers and footers). In PDFs they are checked in
the text that pypdf extracts.

### Documents

| Finding | DOCX | ODT | PDF |
|---|---|---|---|
| Metadata | `core.xml`, `app.xml`, `custom.xml` | `meta.xml` | Info dictionary, XMP |
| Editing time | `TotalTime` | `editing-duration` | |
| Editing cycles | | `editing-cycles` | |
| Save-session identifiers (RSIDs) | count, sessions used by the body text, largest share | | |
| Tracked changes, with names and dates | yes | yes | |
| Comments, with names | yes | yes | |
| Hidden, white and tiny (< 2 pt) text, including through styles | yes | yes | invisible render modes, white fill |
| Fields by type (citation managers included) | yes | | |
| Imported content parts (`altChunk`) | yes | | |
| Embedded objects, macros | yes | yes | |
| Attached template | yes | | |
| Incremental updates, encryption, attachments | | | yes |

## Reading the results

- **Metadata can mislead.** Tools copy properties from their templates. For example, a DOCX
  produced by pandoc carries the application name, editing time and template of pandoc's
  reference document, not of your own work.
- **RSIDs, editing time and editing cycles** are counters kept by the editing software. They
  depend on the editor, start again in a new file, and do not show how the text was written.
  A writing-process record is stronger evidence.
- **Scanned PDFs with text recognition (OCR)** normally contain a layer of invisible text
  over each page image.

## Known limits

- Look-alike letters within a single alphabet, garbled text from wrong encodings, text in
  images and the content of C2PA manifests are not checked yet.
- PDF invisible-text detection follows pypdf's text extraction, which works in chunks: text
  next to invisible or white text in the same chunk may be included.
- Style inheritance is followed for hidden, white and tiny text, but not every way a word
  processor can hide text (for example, text behind images or outside the page).
- Characters a PDF report's font cannot draw are written as `[U+XXXX]`.
