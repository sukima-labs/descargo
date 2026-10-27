# Importing a detector report

`draftwitness import-report` turns the report you downloaded into DraftWitness's
[report format](../schemas/report/0.1.json) (JSON), which the other commands read.
`draftwitness audit` accepts the downloaded PDF directly and runs the same import. The
design is in [ADR 004](adr/004-report-schema.md).

```bash
uv run draftwitness import-report turnitin-report.pdf --out report.json
uv run draftwitness audit turnitin-report.pdf --document my-essay.docx --profile es/uah
```

The file is only read. The JSON records the report's SHA-256, so anyone can check that it
refers to the same file. **Not legal advice.**

## Turnitin

Turnitin's guide
([Downloading and sharing the Similarity Report](https://guides.turnitin.com/hc/en-us/articles/27881575386125))
describes the PDF downloads. DraftWitness reads two of them, in English:

| Layout | How to recognise it | What is read |
|---|---|---|
| Feedback Studio ("Current View") | the paper, then a page headed "ORIGINALITY REPORT" | similarity index; Internet, publication and student-paper figures; the primary sources with their percentages; "Exclude quotes / bibliography / matches"; submission date, ID, word and character counts |
| Enhanced Similarity Report | a Cover Page, then an "Integrity Overview" | overall similarity; filters; exclusions; the four match groups; database figures; integrity flags; the top sources; submission ID, date, pages, words and characters |

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

## Adding a layout or a language

The labels the adapter looks for are in
[`labels.yaml`](../src/draftwitness/adapters/turnitin/labels.yaml). To support a Turnitin
report in another language, add its labels under a new language key and a synthetic test
in `tests/test_turnitin_adapter.py`. Never commit a real report: check it on your own
machine and describe in the pull request which labels you saw.
