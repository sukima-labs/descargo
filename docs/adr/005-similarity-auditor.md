# ADR 005: Similarity auditor — inputs, discount rules and precision

- **Status:** Proposed
- **Date:** 2026-10-27

## Context

A similarity percentage is not a plagiarism finding. Detectors count properly quoted and
cited passages, bibliography entries, assignment templates and the student's own earlier
submissions as "similar", and institutions rarely say which exclusions their settings
applied. The auditor recomputes the percentage after discounting matches that are not
plagiarism, and explains each discount so that an instructor can check it.

Two facts make this harder than it sounds:

1. **Downloaded reports rarely expose match spans.** A Turnitin PDF report shows the overall
   percentage and a per-source list with percentages, but marks the matched text as coloured
   highlighting, which cannot be extracted reliably as text.
2. **Some decisions are the student's or the institution's, not the tool's.** Whether a
   source is the student's own earlier work is something only the student can declare;
   whether reusing it is allowed depends on the institution's rules.

## Options

1. **Span level only:** require match text, refuse to run otherwise. Precise but useless for
   most real reports.
2. **Source level only:** discount whole sources. Works with every report but cannot detect
   quotes or bibliography inside a mixed source.
3. **Two levels:** span-level rules where match text is available, source-level rules where
   it is not, and an explicit precision label on the result.

## Recommendation

Option 3.

### Inputs

- a `Report` (ADR 004);
- optionally, the student's submitted document (DOCX, ODT, PDF or plain text), to locate
  each match in context;
- optionally, an institution profile, for the threshold;
- optionally, a **declarations file** written by the student: sources that are their own
  earlier work (by source label or ID, with a short description), and template or
  assignment-brief text supplied by the institution.

### Discount rules

| Rule | Level | Discounted by default | Evidence shown |
|---|---|---|---|
| Quoted **and** cited: inside quotation marks or a block quote, with a citation marker nearby (`(Author, 2020)`, `[12]`, footnote mark) | span | yes | the passage, the quote marks, the citation found |
| Bibliography: inside the section after a references heading (`References`, `Bibliography`, `Works cited`, `Referencias`, `Bibliografía`, …) | span | yes | the heading and where the section starts |
| Template: matches text the student supplied as institution template or brief | span | yes | the template passage |
| Own declared work: the source is declared by the student as their own earlier work | source or span | yes, with a caveat | the declaration, verbatim |
| Quoted but **not** cited | span | **no**, reported | the passage, flagged as a citation issue, not copying |
| Cited but **not** quoted (close paraphrase) | span | **no**, reported | the passage and the citation |

Own-work discounts always carry a caveat: some regulations require reuse of one's own work to
be disclosed or authorised, so the auditor cites the profile's rule on self-plagiarism when it
has one, and otherwise tells the student to check.

### Computation and precision

- **Exact** (all matches have text and can be located): adjusted % = words in the union of
  non-discounted match spans ÷ total words × 100.
- **Approximate** (some or all discounts are at source level): adjusted % = overall % minus
  the sum of the discounted sources' percentages, floored at 0. This relies on the tool
  attributing each matched passage to a single source, which is how Turnitin's default match
  view works, but overlaps make it an estimate.
- The result states which method was used, and the output never hides the original figure.

### Threshold

The adjusted figure is compared with the profile's threshold for that course or degree. When
the profile has no published threshold, the output says so and states that a percentage does
not by itself establish misconduct. When the threshold is `needs_verification`, the output
says that too.

## Consequences

- The auditor never decides that something *is* or *is not* plagiarism; it applies stated
  rules and shows its work.
- Heuristics (quote detection, reference-heading detection, citation markers) will miss some
  cases. Each rule is a separate function with its own tests, and its patterns live in data
  so that new languages and citation styles can be added without code changes.
- The declarations file is the student's statement. Generated output labels it as such.
