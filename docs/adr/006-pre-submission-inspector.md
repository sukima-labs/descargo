# ADR 006: Pre-submission inspector — what it reports and how

- **Status:** Proposed
- **Date:** 2026-10-27

## Context

Before submitting, a student may want to know what their file contains beyond the visible
text: invisible or unusual Unicode characters (often picked up by copying from a PDF, a web
page or a chatbot), metadata such as author names and editing time, tracked changes, hidden
text, comments, and the save-session identifiers (RSIDs) that some instructors read as
evidence of pasting (`docs/research/2026-10-prior-art.md`, finding 5). Learning about these
after an accusation is too late to explain them calmly.

The same information could serve evasion: a list of "suspicious" characters is also a list
of what to strip. ADR 002 already draws the line: the inspector shows, it never removes. This
ADR settles the questions ADR 002 leaves open.

1. **Judgement.** Should the inspector rate the file (a score, pass/fail), or only describe
   it?
2. **Exit status.** Should findings make the command fail, as a linter would?
3. **Provenance signals.** What should it do with a C2PA text manifest or other data hidden
   in variation selectors?
4. **Wording.** How should it phrase facts that instructors may read as signs of misconduct
   (low RSID count, short editing time, white text)?

## Options

1. **Score and gate.** A risk score and a non-zero exit when findings exist. Familiar from
   linters, but a score is something to optimise against, which turns the inspector into
   a "clean before submitting" loop (ADR 002, non-goal 2), and pass/fail implies a verdict
   DraftWitness cannot give.
2. **Raw dump.** Print every metadata field and code point with no explanation. Honest but
   useless to most students, and silent about what the facts do and do not show.
3. **Described facts, two levels, no score.** Each finding states what was found, where,
   common innocent causes and what it does *not* show. Findings are grouped as **worth
   reviewing** (things a reader or a tool is likely to notice) or **for information**.
   There is no total and no pass/fail.

## Recommendation

Option 3.

- **Levels, not scores.** `review` means "a reader or a tool is likely to notice this", not
  "this is wrong". `info` covers common, usually innocent facts (non-breaking spaces, soft
  hyphens, emoji variation selectors, ordinary metadata). The output never adds them up.
- **Exit status.** 0 whenever the file was read, whatever it contains; 1 only when the
  file cannot be read. Findings are not failures.
- **Provenance signals are reported, never stripped or explained away.** A run of variation
  selectors is decoded into bytes. If the bytes start with the C2PA text wrapper
  (`C2PATXT\0`, version, length, then a JUMBF manifest store, prefixed by U+FEFF: C2PA 2.4,
  Appendix A.8, as implemented by `encypherai/c2pa-text`, MIT), the finding says a content
  credentials manifest is present and gives its size. v0 does not parse or verify the
  manifest. The output does not say how to remove it.
- **No advice on changing the file.** The report never says "remove" or "replace". It
  says DraftWitness has not changed the file, and that if the student edits it with their
  own tools they should keep the original. ADR 002's line holds: showing what a file
  contains is in scope; removing it is not.
- **Wording about process signals.** RSIDs, editing time and editing cycles are described
  as counters kept by the editing software, with their known blind spots (other editors,
  new files, copying between documents), and never as evidence of how the text was written.
  Following the research's finding 3, they are "consistent with" at most, never "proof".
- **Reproducibility.** The output records the file's SHA-256, its size, the DraftWitness
  version and `unicodedata.unidata_version`, because character categories depend on the
  Unicode version (Python 3.12 and Pyodide may differ).

### What v0 inspects

| Format | Checks |
|---|---|
| Text (`.txt`, `.md`) | Characters (below), byte-order mark |
| DOCX | Characters in body, headers, footers, notes and comments; `core.xml`, `app.xml` (including `TotalTime`), `custom.xml`; RSIDs (count in `settings.xml`, sessions used by body text, largest share of body text from one session); tracked changes with authors and dates; comments; hidden (`w:vanish`), white and tiny text, including through styles; fields by type (citation-manager fields included); `altChunk` parts, embedded objects, macros; attached template |
| ODT | Characters in `content.xml` and `styles.xml`; `meta.xml` (including editing cycles and duration); tracked changes; annotations; hidden text and paragraphs; white and tiny text through automatic styles; embedded objects |
| PDF | Characters in the extracted text; Info dictionary and XMP metadata (parsed with defusedxml); end-of-file markers (incremental updates) and linearisation; encryption; attachments; text drawn invisible (render modes 3 and 7) or in white |

Character checks: format characters (zero-width and others), soft hyphens, bidirectional
controls with a per-paragraph balance check (CVE-2021-42574, "Trojan Source"), tag
characters (decoded to the ASCII they spell; emoji subdivision flags are recognised as such),
variation selectors (single ones after a base character are normal; runs are decoded as
hidden data), C0/C1 controls, private-use and unassigned code points, unusual spaces,
fillers that look blank, line and paragraph separators, and words that mix Latin, Greek and
Cyrillic letters.

Left for later: homoglyphs within one script (UTS #39 `confusables.txt`), mojibake
(`ftfy`, CLI extra), parsing C2PA manifests, cross-checks with PyMuPDF or ExifTool, images.

## Consequences

- The inspector can be used to clean a file before submission, and nothing can prevent
  that: the facts it shows are already in the file and visible to any tool. What it will
  not do is remove them, rank them, or tell the student which ones to remove.
- Every finding needs an explanation in each locale; a test checks that every finding kind
  has one.
- PDF invisible-text detection follows pypdf's text extraction, which groups text in
  chunks. Text drawn next to invisible text in the same chunk may be included; the output
  says so.
