# ADR 004: Common report schema (`report_schema`)

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

Every detector (Turnitin, SafeAssign, Copyleaks, GPTZero, …) produces its own report layout.
Modules such as the similarity auditor and the multi-detector comparison must not know about
any of them. Adapters translate each tool's report into one intermediate format, and the
modules only read that format.

The format must be readable by third parties without DraftWitness, so it is published as a
JSON Schema.

## Options

1. **Hand-written JSON Schema as the source**, with Python classes generated from it.
2. **pydantic models as the source**, with the JSON Schema generated from them and committed.
3. **No schema**, just Python dataclasses.

## Decision

Option 2. pydantic models in `draftwitness.core.report_schema` are the single source of
truth. The generated schema is committed as `schemas/report/<version>.json`, and a test fails
if the committed file and the models drift apart. Option 1 makes the Python side awkward and
adds a code generator; option 3 gives third parties nothing to validate against.

### Shape (v0.1)

```text
Report
├─ schema_version   "0.1"
├─ tool             name, product, version, report_kind (similarity | ai_writing | combined)
├─ provenance       adapter name and version, draftwitness version, parsed_at,
│                   sha256 + file name + media type of the downloaded report
├─ submission       title, submission_id, submitted_at, word_count, character_count, page_count
├─ similarity?      overall_percent, filters the tool reports as applied
│                   (quotes / bibliography / small matches excluded),
│                   sources[]  id, rank, label, kind (internet | publication | student_paper
│                              | other | unknown), url, percent, matched_words
│                   matches[]  id, source_id, text, start/end offsets, page, word_count
├─ ai_writing?      overall_percent or label, segments[] (text, offsets, score)
├─ warnings[]       what the adapter could not extract
└─ extensions       tool-specific fields under a namespaced key, e.g. "turnitin"
```

Percentages are numbers from 0 to 100. Offsets refer to the submitted document's extracted
text and are optional, because many downloaded reports do not expose them.

### What the schema records, and what it does not

- It records **what the tool said**, never the student's interpretation. Declarations such
  as "this source is my own earlier work" belong to the auditor's input (ADR 005), not to the
  report.
- **Data minimisation:** no student name, email, student number or instructor name. Adapters
  drop them even when the report shows them. The matched text itself is kept, because the
  audit needs it; it never leaves the device.
- `warnings` makes partial extraction explicit. An adapter must never invent a value it could
  not read; it leaves the field empty and adds a warning.

### Versioning

`schema_version` is `MAJOR.MINOR`. While the major version is 0, a minor bump may break
compatibility, and DraftWitness ships a migration for every older version it can read. From
1.0 on, a minor version only adds optional fields. The schema's `$id` is a URN
(`urn:draftwitness:schema:report:0.1`), so validating against it needs no network.

## Consequences

- Adding a detector means writing an adapter, not changing modules.
- Modules must cope with missing fields (no offsets, no match text) and say so in their
  output.
- The schema files are part of the public contract; changing them needs a version bump.

## Implementation notes: Turnitin PDF adapter v0 (2026-10-27)

These apply the decision to the first adapter without changing it:

- **Layouts.** The adapter reads the two downloadable PDF layouts Turnitin documents: the
  Feedback Studio "Current View" (paper, then an "ORIGINALITY REPORT" page) and the
  enhanced Similarity Report (Cover Page, Integrity Overview, Submission). Anything else is
  refused with an error rather than half-read.
- **Labels in data.** The labels it looks for live in
  `src/draftwitness/adapters/turnitin/labels.yaml`, per layout and language, with where
  each was checked. A label not yet seen in a real report is marked and produces a warning
  when it is used.
- **No match text.** Both layouts show matched passages only as coloured highlights, so the
  report has sources and no matches, and the auditor uses its approximate method (ADR 005).
- **Data minimisation.** The author name and the file name shown on the report are not
  kept. On the enhanced cover page the title and the author name appear in an order that
  varies, so a line is kept as the title only when it equals the file name (Turnitin's
  default title); otherwise neither is kept and a warning says so.
- **Tool-specific facts** go under `extensions.turnitin`: the layout, the per-database
  breakdown, and for the enhanced layout the match groups, exclusions and integrity flags.
- **Consistency checks** only use rules that hold for every report: no single source can
  exceed the overall figure. Per-database figures can exceed it (they overlap), so they are
  not checked.
- **Real reports** used to check the layouts are never committed; tests use synthetic PDFs
  with the same line structure.
