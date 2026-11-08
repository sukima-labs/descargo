# Importing a detector report

*[Español](../import.md) · English*

`descargo import-report` turns the report you downloaded into Descargo's
[report format](../../schemas/report/0.1.json) (JSON), which the other commands read.
`descargo audit` accepts the downloaded PDF directly and runs the same import. The
design is in [ADR 004](../adr/004-report-schema.md).

```bash
uv run descargo import-report turnitin-report.pdf --out report.json
uv run descargo import-report informe-compilatio.pdf --out report.json
uv run descargo audit turnitin-report.pdf --document my-essay.docx --profile es/uah
```

The file is only read. The JSON records the report's SHA-256, so anyone can check that it
refers to the same file. **Not legal advice.**

## Turnitin

Turnitin's guide
([Downloading and sharing the Similarity Report](https://guides.turnitin.com/hc/en-us/articles/27881575386125))
describes the PDF downloads. Descargo reads three of them:

| Layout | How to recognise it | What is read |
|---|---|---|
| Feedback Studio ("Current View"), in English and Spanish | the paper, then a page headed "ORIGINALITY REPORT" ("INFORME DE ORIGINALIDAD") | similarity index; Internet, publication and student-paper figures; the primary sources with their percentages; "Exclude quotes / bibliography / matches"; submission date, ID, word and character counts |
| Enhanced Similarity Report, in English and Spanish | a Cover Page ("Portada"), then an "Integrity Overview" ("Descripción general de integridad") | overall similarity; filters; exclusions; the four match groups (English only); database figures; integrity flags and what the report says about each, such as hidden text; the top sources; submission ID, date, pages, words and characters; the sections the PDF contains |
| AI Writing Report, in English and Spanish, on its own or after the Similarity Report in the same PDF | an "AI Writing Overview" ("Descripción general de la escritura con IA") opening with "23% detected as AI" ("detectado como IA") | the share of text attributed to AI, or "*%" when it is under Turnitin's 20 % threshold; the two detection groups (English only); the passages highlighted in cyan, page by page; the same submission details as the Similarity Report |

Not kept: the author name and the file name shown on the report. On the enhanced cover
page, the title is kept only when it is the file name (Turnitin's default), because the
title and the author name appear in an order that varies.

Every import says what it could not read. In particular:

- **No matched text.** Turnitin PDFs show matched passages as coloured highlights, which
  cannot be extracted reliably, so the audit uses its approximate method
  ([ADR 005](../adr/005-similarity-auditor.md)).
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
maintainer's machine only ([ADR 009](../adr/009-first-three-detectors.md)): one in English and
four in Spanish (one full, three extracts, one of them reprinted through Word).

The AI Writing Report was checked in November 2026 against three real reports read on the
maintainer's machine only: two in English (23 % and 0 %) and one in Spanish, after its
Similarity Report, with a score under the threshold. On the English 23 % report, the
highlighted passages make 6 runs and 473 words, about 17 % of all the words on the paper's
pages; Turnitin's 23 % is a share of the text its model qualifies, which leaves out tables,
lists and references. About the AI Writing Report:

- **The result is the tool's.** The import records it as Turnitin states it and the audit
  does not recompute it ([ADR 009](../adr/009-first-three-detectors.md)).
- **"\*%"** means the score is under 20 %: Turnitin then gives no figure and highlights
  nothing, because, as the report says, such scores are more likely to be false positives.
  The import keeps "\*%" as the label shown.
- **Passages are read by the highlight behind them,** a piece of text at a time, so a
  passage that starts or ends inside a line may gain or lose a few words there.
- **Paraphrased text is not read yet.** Turnitin highlights text that was also
  AI-paraphrased in purple, a colour no real report has shown so far; when that group is
  above 0 %, the import says those passages are missing.
- **In a PDF with both reports,** only the AI Writing Report's own pages are searched for
  highlights, told apart by the page total in their footers.

The Spanish Feedback Studio layout was checked in November 2026 against three real reports of
May, June and August 2026, read on the maintainer's machine only. All three read with
every source paired with its percentage (2, 50 and 61 sources). The reports wrap the
title over two lines and print the author further down ("por …"); the title is kept as
Turnitin prints it again on one line above "INFORME DE ORIGINALIDAD", and the author is
dropped. Some print two switches on one line ("Excluir citas Apagado Excluir coincidencias
Apagado"), and "TRABAJOS DEL ESTUDIANTE" on one line or two; both are read. A fourth
Spanish report, reprinted through Word as images, has no text to read.

**Known gap.** Scanned or image-only copies of a report have no text to read.

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
  `descargo inspect` shows both kinds of content in your own file.
- Turnitin's **Submission Details** show investigators the file's author, "last modified
  by", paper size, software, fonts and a count of American and British spellings
  ([Submission Details and Document Details](https://guides.turnitin.com/hc/en-us/articles/30872471895821)).

## Compilatio

Descargo reads Compilatio's analysis report PDF in Spanish, in its two layouts. Both
were learned from real reports read on the maintainer's machine only
([ADR 009](../adr/009-first-three-detectors.md)): three Magister reports of September to
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

## Copyleaks

Descargo reads the PDF Copyleaks exports, in English, in two layouts. They were learned
from four real reports read only on the project maintainer's machine
([ADR 009](../adr/009-first-three-detectors.md)): the sample Copyleaks published in October
2022, two samples from its website of April and June 2023, and a report a blog published in
May 2023. The three from 2023 were recovered from the Internet Archive.

### 2023 ("Plagiarism and AI Content Detector Report" or "Plagiarism report")

| Part of the report | What is read |
|---|---|
| "Scan details" | document title, page and word counts; the scan date, as an extension |
| "Plagiarism Detection" | the overall similarity and its split into identical, minor changes, paraphrased and omitted words, with their percentage and words |
| "AI Content Detection" | the percentage and words of AI text and of human text. If the report shows "N/A", it has no AI result, and the import says so |
| "Alerts" | each alert's title and severity ("2/5 Severity") |
| "Plagiarism Results" | each source with its title, URL and percentage. When the report splits a source's percentage by match type, that split is kept and the percentage is its sum: the report's overall similarity is likewise the sum of its types (checked on the three real reports). Sources from the "Copyleaks Internal Database" are marked `other` |
| "Scanned AI content" | the passages drawn on the darkest step of Copyleaks' AI scale, with their page. On the sample with 100 % AI, their words match the count Copyleaks gives |

### 2022

The earlier layout has the overall similarity, the words by match type, the sources and
the scan date, with no AI result. It prints the source percentages in a column apart from
the names: they are paired in order, and the import warns if the counts differ.

Neither layout keeps who submitted the scan ("Submitted by") or the scan id ("Scan id").

What it cannot read:

- **No matched text.** Matched passages are highlighted by type, but the highlight does not
  say which source they match, so the audit uses its approximate method.
- **Lighter shades of the AI scale.** Copyleaks colours AI passages on a scale from 20 % to
  99 %, and only the 99 % shade has been seen in a real report. If the passages read do not
  add up to the percentage Copyleaks gives, the import warns that lighter-shaded passages
  may be missing.
- **Other languages and the current layout.** Only English reports up to 2023 have been
  seen.

The audit shows the AI figure and passages as what the tool claims. It does not recompute
or discount them.

## Adding a layout or a language

The labels the adapters look for are in `labels.yaml` next to each adapter
([Turnitin](../../src/descargo/adapters/turnitin/labels.yaml),
[Compilatio](../../src/descargo/adapters/compilatio/labels.yaml),
[Copyleaks](../../src/descargo/adapters/copyleaks/labels.yaml)). To support a report in
another language, add its labels under a new language key (for Compilatio, under its
layout) and a synthetic test in `tests/test_<tool>_adapter.py`. Never commit a real report: check it on your own
machine and describe in the pull request which labels you saw.
