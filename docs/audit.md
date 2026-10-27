# Similarity audit

`draftwitness audit` recomputes a similarity percentage after discounting matches that are
not plagiarism, and explains every discount. It applies rules and shows its evidence. It
never decides whether something is or is not plagiarism, and it never hides the report's
own figure. The design is in [ADR 005](adr/005-similarity-auditor.md).

**Not legal advice.**

## Inputs

| Input | Required | What it is for |
|---|---|---|
| `REPORT` | yes | The detector report: a Turnitin Similarity Report or Compilatio analysis report PDF as downloaded (see [`import.md`](import.md)), or DraftWitness JSON ([report schema](../schemas/report/0.1.json)). |
| `--document` | no | Your submitted work (`.docx`, `.odt`, `.pdf`, `.txt`, `.md`). It is used to find each matched passage in context. Without it, only declaration-based rules apply. |
| `--declarations` | no | Your statements: your own earlier work and institution template text. See [`examples/declarations.example.yaml`](../examples/declarations.example.yaml). |
| `--profile`, `--path` | no | Institution profile used for the threshold comparison and the rule on reusing your own work. |

Files are only read. The output (`--format md|json|pdf`, `--out FILE`) records the SHA-256
of every input, so anyone can check that the audit refers to the same files.

## Rules

| Rule | Discounted | Evidence shown |
|---|---|---|
| Quoted **and** cited: inside quotation marks (“ ”, « », " ", „ “, ‘ ’) or a block quotation, with a citation nearby | yes | the marks and the citation found |
| Reference list: after the last references heading in the body, up to an appendix heading | yes | the heading |
| Institution template: part of text you declared | yes | your template description |
| Your own earlier work: a source you declared | yes, with a caveat citing your institution's rule when the profile has one | your declaration, verbatim |
| Quoted but no citation found | **no**, reported | the passage |
| Citation found but no quotation marks | **no**, reported | the passage and the citation |

Citation styles recognised:

- author–date (APA, Harvard, Chicago), including Spanish "y", "s. f." and "pág.";
- narrative citations such as `Smith (2020)`;
- MLA;
- IEEE `[n]` and Vancouver `(n)`;
- superscript digits;
- Ibid., Ibíd. and op. cit.;
- DOIs;
- DOCX and ODT footnote and endnote references.

The patterns live in
[`rules.yaml`](../src/draftwitness/modules/post/audit/rules.yaml). To add a language or a
style, add a pattern there and an example to `tests/test_audit_rules.py`.

## Exact and approximate figures

- **Exact:** every match listed in the report was found in your document, and together they
  add up to the report's figure (within 2 points). Discounts are then measured in words.
- **Approximate:** some matches are missing from the report, or no document was given.
  - Whole sources subtract their reported percentage.
  - Passages subtract their share of the report's word count, capped at their source's
    percentage.
  - Sources shown as `<1%` are not subtracted.

When in doubt, the auditor discounts less, never more.

## Known limits

- Quotation and citation detection are heuristics. They miss unusual layouts and can pair a
  quotation with a neighbouring citation. Each discount shows its evidence so that a person
  can check it.
- Block quotations are recognised from a paragraph style (Quote, Cita, Quotations) or a
  Markdown `>` prefix, not from indentation.
- PDFs give no paragraph styles, so block quotations in PDFs are not recognised.
- Word counts differ slightly between tools. The exact method subtracts discounted points
  from the report's own figure for that reason.
