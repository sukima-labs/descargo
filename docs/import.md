# Importing a detector report

`draftwitness import-report` turns the report you downloaded into DraftWitness's
[report format](../schemas/report/0.1.json) (JSON), which the other commands read.
`draftwitness audit` accepts the downloaded PDF directly and runs the same import. The
design is in [ADR 004](adr/004-report-schema.md).

```bash
uv run draftwitness import-report turnitin-report.pdf --out report.json
uv run draftwitness import-report informe-compilatio.pdf --out report.json
uv run draftwitness audit turnitin-report.pdf --document my-essay.docx --profile es/uah
```

The file is only read. The JSON records the report's SHA-256, so anyone can check that it
refers to the same file. **Not legal advice.**

## Turnitin

Turnitin's guide
([Downloading and sharing the Similarity Report](https://guides.turnitin.com/hc/en-us/articles/27881575386125))
describes the PDF downloads. DraftWitness reads two of them:

| Layout | How to recognise it | What is read |
|---|---|---|
| Feedback Studio ("Current View"), in English | the paper, then a page headed "ORIGINALITY REPORT" | similarity index; Internet, publication and student-paper figures; the primary sources with their percentages; "Exclude quotes / bibliography / matches"; submission date, ID, word and character counts |
| Enhanced Similarity Report, in English and Spanish | a Cover Page ("Portada"), then an "Integrity Overview" ("Descripción general de integridad") | overall similarity; filters; exclusions; the four match groups (English only); database figures; integrity flags and what the report says about each, such as hidden text; the top sources; submission ID, date, pages, words and characters; the sections the PDF contains |

Not kept: the author name and the file name shown on the report. On the enhanced cover
page, the title is kept only when it is the file name (Turnitin's default), because the
title and the author name appear in an order that varies.

Every import says what it could not read. In particular:

- **No matched text.** Turnitin PDFs show matched passages as coloured highlights, which
  cannot be extracted reliably, so the audit uses its approximate method
  ([ADR 005](adr/005-similarity-auditor.md)).
- **Shortened names.** The enhanced report cuts long source names, ending them in "...".
- **Unchecked labels.** Filter names that have not yet been seen in a real report produce
  a warning when they appear.

- **Extracts.** When the PDF has fewer pages than the report's footers say ("Page 2 of
  13"), the import says it is an extract and that parts may be missing.
- **Reprints.** A report saved again through another program, such as Word, may lose the
  numbers of its source list; the import says so. Use the PDF downloaded from Turnitin.
- **Spanish reports print no counts** for excluded matches and integrity flags
  ("N.º de coincidencias excluidas"), so those counts stay empty.

The enhanced layout was checked in October 2026 against five real reports read on the
maintainer's machine only ([ADR 009](adr/009-first-three-detectors.md)): one in English and
four in Spanish (one full, three extracts, one of them reprinted through Word).

**Known gap.** Turnitin's AI writing report ("detected as AI", "detectado como IA") and the
Spanish Feedback Studio layout ("Fecha de entrega", "Identificador de la entrega") are not
read yet ([ADR 009](adr/009-first-three-detectors.md)). Scanned or image-only copies of a
report have no text to read.

### Facts from Turnitin's documentation worth knowing

- When the same words match several sources, the report shows **one top source** for them,
  preferring Internet, then Publications, then Submitted Works
  ([Navigating the new, enhanced Similarity Report](https://guides.turnitin.com/hc/en-us/articles/27395528629517)).
  The approximate audit relies on this.
- **Match groups** ("Cited and Quoted", "Missing Citation"…) are produced by models trained
  on English, are available only for submissions in English, and recognise APA, MLA,
  Turabian and IEEE citations
  ([How do the Match Groups work](https://guides.turnitin.com/hc/en-us/articles/28057483210637)).
  For work in Spanish they say nothing about how well it is cited.
- **Integrity flags** cover hidden text and replaced characters
  ([Integrity Flags](https://guides.turnitin.com/hc/en-us/articles/27397357797517)).
  `draftwitness inspect` shows both kinds of content in your own file.
- Turnitin's **Submission Details** show investigators the file's author, "last modified
  by", paper size, software, fonts and a count of American and British spellings
  ([Submission Details and Document Details](https://guides.turnitin.com/hc/en-us/articles/30872471895821)).

## Compilatio

DraftWitness reads Compilatio's analysis report PDF in Spanish, in its two layouts. Both
were learned from real reports read on the maintainer's machine only
([ADR 009](adr/009-first-three-detectors.md)): three Magister reports of September to
December 2025, and five Magister+ reports and one certificate of March to July 2026.

### Magister (until 2025, "INFORME DE ANÁLISIS")

| Part of the report | What is read |
|---|---|
| Results on the first page | similarity (the overall figure); "Textos potencialmente generados por la IA"; also, kept as extensions, suspicious text, similarity in quotes, similarity with cited sources and unrecognised languages. A result marked "(ignorado)" is listed in `marked_ignored` |
| Document details | document name (as the title, without its extension), word and character counts, deposit and analysis dates |
| "Fuentes principales detectadas" and "Fuentes con similitudes fortuitas" | each source with its label, URL (when not shortened), percentage and identical words; which table it came from |
| "Fuentes mencionadas" | the URLs the document cites without any similarity |
| The document pages | the passages drawn in the colour Compilatio uses for AI, with their page |

### Magister+ (from 2026, "Informe de análisis" and "Certificado de análisis")

| Part of the report | What is read |
|---|---|
| Section 1, the summary | suspicious text; similarity, with its "Sintáctica" and "Semántica" split; "Detección de IA"; unrecognised languages; text in quotes; and, for each, whether the report counts it in the suspicious-text percentage ("Incluido" or "No incluido") |
| Document details | file name (as the title, without its extension), word and character counts, deposit and analysis dates |
| Section 2, the sources | each source with its label, URL (as shown, without "https://", when not shortened) and percentage; which table it came from ("Fuente principal detectada" or "Fuente con similitudes fortuitas"); whether it is another user's document or one of the account's library, and whether it was found by semantic detection |
| "Fuente mencionada (sin similitudes detectadas)" | the URLs the document cites without any similarity |
| Section 3, the document (full report only) | the passages underlined in the colour Compilatio uses for AI, with their page |

The certificate has sections 1 and 2 only, so it has no AI passages; the import says so.
The source tables come out of the PDF a column at a time, so each row is put back together
from where its pieces are drawn.

Not kept, in either layout: the depositor's name, the document ID, the original file size
and the upload type.

What it cannot read:

- **No matched text.** Matched passages are highlighted behind the text, which the PDF's text
  does not expose, so the audit uses its approximate method, as with Turnitin.
- **AI passages come from a colour or an underline.** Check them against the report; the
  import says so. In the real reports, the words in the passages read came within one
  percentage point of the AI figure Compilatio gives.
- **Bounds.** "< 1 %" is kept as 1 % with the upper-bound flag.
- **Reports copied into another document.** A certificate pasted into a thesis PDF is not
  read; use the PDF downloaded from Compilatio.

The audit shows the AI figure and the passages as the tool's statement. It does not
recompute or discount them.

## Adding a layout or a language

The labels the adapters look for are in `labels.yaml` next to each adapter
([Turnitin](../src/draftwitness/adapters/turnitin/labels.yaml),
[Compilatio](../src/draftwitness/adapters/compilatio/labels.yaml)). To support a report in
another language, add its labels under a new language key (for Compilatio, under its
layout) and a synthetic test in `tests/test_<tool>_adapter.py`. Never commit a real report: check it on your own
machine and describe in the pull request which labels you saw.
