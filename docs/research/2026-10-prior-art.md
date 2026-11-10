# Prior art and reusable open-source components (October 2026)

- **Date:** 2026-10-27
- **Note:** the project was called DraftWitness until 2026-11-05; this document uses the current name.
- **Scope:** open-source projects that overlap with Descargo, and open-source libraries,
  data and formats we could incorporate. Closed tools are listed only to map the landscape.
- **Method:** repository pages, the GitHub API and PyPI metadata, checked on the date above.
  Nothing was installed or run. Licences marked ✔ were re-checked by the maintainer after
  the survey. Everything else should be re-checked before it is adopted.

Compatibility with AGPL-3.0-or-later uses the usual rules:

- **Compatible:** MIT, BSD, ISC, 0BSD, Apache-2.0, MPL-2.0, LGPL/GPL "or later",
  GPL-3.0, AGPL-3.0, CC0 and the Unicode License v3.
- **Not compatible:** GPL-2.0-only, non-commercial or "academic only" terms,
  CC BY-SA 3.0, and repositories with no licence.
- **Separate programs:** tools called as separate programs (subprocess, a localhost server)
  are aggregation, not combination.

## Findings

1. **No open-source project covers the same ground.** None combines access requests,
   report auditing, metadata and invisible-character inspection, and appeal dossiers for
   students. No open FERPA or Colombian habeas-data letter generator was found. The open
   projects that overlap each cover one piece:
   - writing-process recorders;
   - policy datasets;
   - GDPR letter templates.
2. **The space is crowded with tools that conflict with our non-goals.**
   - Humanizers and "detector bypass" tools lead GitHub search results for "turnitin"; the
     top one has about 8,200 stars.
   - "Watermark cleaners" and RSID sanitisers are common.
   - Report forgers exist, such as `turnitin-pdf-stamper`.

   The README should say plainly that Descargo is not one of these.
3. **Process evidence can be simulated.**
   - drafttrace-benchmark (MIT code, CC BY data) shows that a typing humanizer falls inside
     the timing range of 151 real writers.
   - DocuSim fakes Google Docs revision history.

   Our wording must be "consistent with" or "contemporaneous record", never "proof".
   Third-party timestamps and independent sources should weigh more than keystroke timing.
4. **Forged reports exist on both sides,** so the auditor records the report's hash and
   where it came from at intake.
5. **Instructors already read DOCX RSIDs** (save-session identifiers) as evidence of
   pasting. The inspector should count them and explain what they do and do not show.
6. **Vendors hold writing-process logs,** for example Cursive in Moodle, Turnitin Clarity,
   GPTZero and Grammarly Authorship. These are personal data the access letters should
   ask for.

## Decisions by need

Codes: **ADOPT** = runtime dependency (Pyodide-compatible). **EXTRA** = optional,
CLI-only. **BORROW** = reimplement the idea, algorithm, format or data with attribution.
**AVOID**.

### Report-access requests (step 5, follow-ups in phase 2)

| Component | Licence | Decision |
|---|---|---|
| [datenanfragen/data](https://github.com/datenanfragen/data) templates and authority records | CC0-1.0 ✔ | **BORROW.** Its `templates/es` folder has `access-default`, `access-tracking`, `admonition`, `complaint`, `erasure-default`, `objection-default` and `rectification-default`. It also has authority records for the AEPD (`esaepa.json`) and the ICO (`gbico.json`). Use them for the follow-up reminder and the complaint to the authority, and to cross-check our EU/ES letter. Its Spanish uses "vosotros"; we write in "usted". It has no records for detector vendors, which we could contribute upstream. |
| [datenanfragen/website](https://github.com/datenanfragen/website) | MIT | **BORROW the idea.** A client-side generator is the model for the Pyodide build, and it follows up with a tracking code. |
| Michael Veale's Art. 15 template (michae.lv/access-template) | CC0-1.0 | **BORROW** checklist items: inferences and derived data, named recipients, and the logic of automated decision-making. |
| My Data Done Right, personaldata.io | no licence found | **AVOID copying.** Link to them only. |

### Similarity auditor (step 6)

| Component | Licence | Pyodide | Decision |
|---|---|---|---|
| [`regex`](https://pypi.org/project/regex/) | Apache-2.0 AND CNRI-Python ✔ | shipped ✔ | **ADOPT.** Gives Unicode properties (`\p{Lu}` matches "Álvarez"), which citation patterns in Spanish and English need, and fuzzy matching for short passages. |
| [`syntok`](https://pypi.org/project/syntok/) | MIT ✔ | pure Python (needs `regex`) | **Later.** A Spanish, English and German sentence splitter that keeps offsets. Adopt it when a rule needs sentences; v0 uses windows. |
| `pysbd` | MIT | pure Python | Fallback to syntok; unmaintained since 2021. |
| stdlib `difflib` | PSF | yes | **ADOPT.** Fuzzy location when an exact normalised match fails. |
| `rapidfuzz` | MIT | not shipped ✔ | **EXTRA** later, as a speed-up only. |
| GROBID (Java server), AnyStyle (Ruby) | Apache-2.0, BSD-2 | no | **EXTRA** later, against a local server or process only; never a remote demo server. |
| CERMINE, refextract | AGPL-3.0, GPL-2.0+ | no | **AVOID.** CERMINE is stale; refextract is physics-specific and fetches URLs. |
| CSL locale files | CC BY-SA 3.0 | — | **AVOID copying.** Use them as a checklist of terms such as "y", "s. f." and "pág.". |
| Crossref DOI pattern | fact | — | **BORROW.** Use it in the bibliography and citation patterns. |

Patterns live in data, as ADR 005 requires. They cover:

- APA, Harvard and Chicago author-date, with Spanish "y", "s. f." and "pág.";
- MLA `(Smith 23)`;
- IEEE `[n]` and Vancouver `(n)`;
- note references (DOCX `w:footnoteReference`, ODT `text:note`) and Ibid., Ibíd., op. cit.;
- reference-section headings in Spanish and English.

### Pre-submission inspector (step 7)

| Component | Licence | Pyodide | Decision |
|---|---|---|---|
| Our own OOXML and ODF reader (`zipfile` + `defusedxml`) | — / PSFL ✔ | yes | **BUILD.** python-docx hides exactly what an inspector needs, and odfpy is stale and ships no wheel. `defusedxml` becomes an explicit dependency. |
| `pypdf` (already a dependency) | BSD-3 | pure Python | **Keep** for Info and XMP metadata, attachments and encryption. A content-stream visitor catches invisible (`Tr 3`) and white text; incremental updates are counted on the raw bytes. |
| [wppoland/hidden-text-detector](https://github.com/wppoland/hidden-text-detector) | MIT ✔ | — | **BORROW** its rules for hidden text at render level: white on white, tiny fonts, off-page text, Word's hidden attribute and tag characters. Also a source of test cases. |
| [encypherai/c2pa-text](https://github.com/encypherai/c2pa-text) | MIT ✔ | — | **BORROW** its decoding. Report C2PA text manifests carried in variation selectors, and never strip them. |
| stdlib `unicodedata` | PSF | yes | **ADOPT.** Record `unidata_version` in every report, because Python 3.12 and Pyodide differ. |
| UTS #39 `confusables.txt` | Unicode License v3 | data | **BORROW** a vendored snapshot for homoglyph and mixed-script checks, together with `regex` script properties. Later. |
| `confusable_homoglyphs` | MIT | — | **AVOID.** It downloads data from unicode.org when its data is missing. |
| `ftfy` | Apache-2.0 | pure Python | **EXTRA,** later: flag mojibake only, never fix it. |
| PyMuPDF, pdfminer.six, ExifTool | AGPL-3.0, MIT, Perl terms | no, yes, no | **EXTRA** cross-checks later. |
| hachoir | "GPL v2" (only?) | — | **AVOID.** |

What the inspector reports, as facts, never fixes:

- **DOCX:**
  - `core.xml`, `app.xml` and `custom.xml`, including `TotalTime` editing minutes;
  - the RSID count;
  - tracked changes, hidden text, comments and fields;
  - `altChunk` parts and embedded objects.
- **ODT:**
  - `meta.xml`, including editing cycles and editing duration;
  - tracked changes, hidden text and annotations.
- **PDF:** Info and XMP metadata, incremental updates, and invisible text.
- **Text:**
  - format characters such as zero-width spaces;
  - bidi controls, with a balance check against Trojan Source;
  - tag characters (U+E0000–E007F);
  - variation selectors;
  - controls, private-use and unassigned code points;
  - unusual spaces and fillers.

### Evidence package (phase 2)

| Component | Licence | Pyodide | Decision |
|---|---|---|---|
| `cryptography` | Apache-2.0 OR BSD-3 | shipped ✔ | **ADOPT** for Ed25519. Signatures use the minisign format (`ED` = Ed25519 over BLAKE2b-512, plus a trusted comment), so the stock `minisign` tool can verify them. |
| BagIt (RFC 8493), in-toto Statement v1 | public domain, Apache-2.0 | — | **BORROW the formats** for the bundle layout and the manifest. `bagit` is used only as a test-time validator. |
| `repro-zipfile` | MIT | pure Python | **ADOPT or BORROW** for deterministic archives. |
| `rfc3161-client` (Trail of Bits), `asn1crypto` | Apache-2.0, MIT | no, yes | **EXTRA,** with an explicit opt-in flag. `asn1crypto` parses a `.tsr` offline. |
| python-opentimestamps | LGPL-3.0+ | no (`pycryptodomex`) | **EXTRA,** opt-in. Version 0.5.0 was uploaded on the survey date; review it before pinning. |
| sigstore | Apache-2.0 | no | **AVOID for student evidence**: it puts the signer's identity in a public log. It is fine for signing our own releases. |
| c2pa-python, rfc3161ng | MIT/Apache, MIT | no | **AVOID.** |
| [ArgLab/writing_observer](https://github.com/ArgLab/writing_observer) `reconstruct_doc.py` | AGPL-3.0 ✔ | stdlib only | **BORROW or port.** It rebuilds Google Docs text from the changelog JSON that the student exports themselves. Our tool never fetches it. |
| WriteProof `.writeproof.json`, Obsidian Replay `.replay`, Cursive JSON | MIT, 0BSD, GPL-3.0+ | — | **Import formats.** Descargo should be a neutral verifier and packager for these, plus RSIDs and git history, rather than yet another recording editor. |
| HuManuScript, DraftProof, Writermark and similar | no licence or source-available | — | **Ideas only.** Copy HuManuScript's habit of printing the evidence's own limits on every export. |

### Stylometry (phase 2)

Authorship verification is not reliable enough to clear or convict an individual. It breaks
down on short texts and across genres, and it can be turned against the student. If we offer
it, it is off by default and descriptive only, with no probability and no verdict.

| Component | Licence | Decision |
|---|---|---|
| faststylometry | MIT | **BORROW** Burrows' Delta. It pins Python ≤ 3.13.3, which rules out Pyodide. |
| PAN `pan-code` | MIT | **BORROW** the evaluation measures and the baselines: character n-gram cosine and compression distance. |
| JGAAP (AGPL, Java), stylo (GPL, R) | compatible | Method references and offline validation only. |

### AI detectors (post-submission comparison only)

Running a detector on a draft amounts to predicting the score, which is a non-goal. The
comparison module therefore compares scores the institution has already produced, and
cites the literature. Open detectors are impractical locally anyway:

- Binoculars needs two 7B models and is "academic only".
- Ghostbuster sends text to OpenAI.
- RADAR is licensed for non-commercial use only.

Sources for the appeal dossier:

| Source | What it shows |
|---|---|
| Liang et al. 2023, *Patterns* (arXiv 2304.02819) | Seven detectors on TOEFL essays: average false-positive rate 61.22%; 97.8% of essays flagged by at least one detector |
| Weber-Wulff et al. 2023, *Int. J. Educ. Integrity* 19:26 | Fourteen tools, Turnitin among them, are "neither accurate nor reliable" |
| Turnitin's own blog | Vendor's own figure of about 4% sentence-level false positives |
| RAID (ACL 2024) | Detectors are easily fooled |
| Vanderbilt notice, 2023-08-16 | Disabled Turnitin's AI detector |

Two counterpoints the dossier must handle carefully:

- A 2026 thesis (LRIaiza/AI-Detect, Apache-2.0) traces one "non-native bias" result to
  corpus genre rather than to whether the writer is a native speaker.
- ETS reports purpose-built detectors with near-zero bias. That paper was not retrieved.

Do not cite benchmarks run by humanizer vendors.

### Policy data (profiles)

| Source | Licence | Decision |
|---|---|---|
| [SciWhite/university-ai-policy-tracker](https://github.com/SciWhite/university-ai-policy-tracker) | code Apache-2.0 ✔, data CC BY 4.0 | **Leads only.** It has 815 universities, including UT Austin, Los Andes and Nacional de Colombia, but not Alcalá. Its records are reviewed by AI agents, not by people. Its evidence model is worth borrowing: official URL, snapshot hash and the quote in the original language. |
| ZhichengLin/university-ai-policy-dataset | MIT | Background: coded threshold policies for Chinese universities. |
| inducer/uiuc-academic-integrity | no licence | Read only, to see how the institution side runs hearings. |

## Effect on the roadmap

- **Step 6, auditor:**
  - add `regex` and make `defusedxml` explicit;
  - keep the patterns in data;
  - fall back to `difflib` for fuzzy location;
  - treat DOCX and ODT note references and superscript runs as citation markers;
  - hash every input.
- **Step 7, inspector:** build our own OOXML and ODF reader. It reports the RSID count,
  editing time, C2PA text manifests, tag characters, bidi balance and `unidata_version`.
- **Access requests:** add writing-process logs to the items requested. In phase 2, reminder
  and complaint letters, starting from the CC0 datenanfragen templates.
- **Phase 2, evidence:**
  - minisign-format signatures with `cryptography`;
  - BagIt and in-toto layout;
  - importers for Google Docs changelogs, `.writeproof.json`, `.replay`, RSIDs and git;
  - wording that states the evidence's limits.
- **README:** a section on how Descargo differs from humanizers and report forgers.
