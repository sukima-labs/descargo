# Changelog

All notable changes to Descargo are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Before 1.0, any minor version
may break the command line, the profile format or the report format.

## [Unreleased]

Nothing has been released yet. Phase 1 is in progress; the package version is
`0.1.0.dev0`.

### Added

- Web page: a new tab, «Si te acusan» / "If you are accused", shows the procedure guide of
  the chosen country (Spain, Colombia, Mexico, Argentina, Chile, Peru) in Spanish or
  English. The build turns `docs/procedimientos*.md` and `docs/en/procedures*.md` into
  `guides.json`, blocks the page draws with DOM calls (no HTML is inserted). Links between
  guides switch the country, links to sections scroll to them, and a test checks every
  link resolves.
- Copyleaks adapter (`copyleaks-pdf` 0.1). It reads the English PDF report Copyleaks
  exported in 2023 ("Plagiarism and AI Content Detector Report" or "Plagiarism report"):
  overall similarity split by match type, sources with their shares, alerts, the AI and
  human shares, and the passages drawn on the darkest step of Copyleaks' AI scale. It also
  reads the 2022 export, which has no AI result. It never keeps who submitted the scan or
  the scan id. Learned from four real reports, three of them recovered from the Internet
  Archive; the tests use synthetic PDFs only. The code that reads text on highlight
  rectangles moved from the Turnitin AI adapter to `adapters/highlights.py`, shared by both.
- Procedures guide for Peru (`docs/procedimientos-pe.md`, English in
  `docs/en/procedures-pe.md`). Unlike the other countries, the Ley Universitaria sets a
  national minimum: disciplinary proceedings, three possible sanctions, and a Tribunal de
  Honor (Ley 30220 arts. 75, 99, 101; Constitution art. 18). For public universities, the
  sanctioning chapter of Ley 27444 (TUO arts. I, 247, 248, 252, 255). PUCP is the worked
  example: plagiarism is defined and is a serious offence, and the guide covers the stages,
  deadlines and appeals (Reglamento Unificado arts. 6, 31, 33, 46, 47, 57-76, Annex 2).
  Amparo: Constitution art. 200.2 and Ley 31307 arts. 7, 43 and 45. Each quote checked in
  the official text on 2026-11-08. On 2026-11-10 the guide also gives two Tribunal
  Constitucional judgments on amparo against university sanctions (Exp. 01981-2011-PA/TC:
  expulsion annulled for lack of reasons and defence; Exp. 00029-2015-PA/TC: rule-based
  academic removal upheld), read in full; none concerns plagiarism.
- Procedures guide for Chile (`docs/procedimientos-cl.md`, English in
  `docs/en/procedures-cl.md`). Constitution art. 19 no. 3 (legal defence, a rational and
  fair procedure). The Universidad de Chile is the worked example: the student duty to
  acknowledge the source and authorship of ideas (Reglamento de Estudiantes art. 3 no. 6),
  and the ordinary and simplified disciplinary procedures, sanctions and appeal (D.U.
  0026685 of 2019, arts. 1, 9, 11-19, 21, 29, 30, 32, 35, 39, 43). Recurso de protección:
  Constitution art. 20 and the Supreme Court's Acta 94-2015 (30 calendar days). Each quote
  checked in the official text on 2026-11-08. On 2026-11-10 the guide also reports, from
  press notes only, two Supreme Court rulings on how that deadline is counted (Rol
  4309-2026: from the rejection of an internal reposición; Rol 8.270-2026: an outside
  complaint does not suspend it) and advises counting from the first notification.
- Procedures guide for Argentina (`docs/procedimientos-ar.md`, English in
  `docs/en/procedures-ar.md`). Each university sets its own disciplinary rules
  (Constitution arts. 18 and 75.19; Ley 24.521 arts. 14 and 29). UBA is the worked example:
  offences, sanctions and limitation periods, and the stages and deadlines of the
  disciplinary inquiry (Código UBA arts. 503-519, from Resolución CS 2283/88). Judicial
  appeal against final decisions of national universities: Ley 24.521 art. 32. Each quote
  checked in the official text on 2026-11-08. On 2026-11-10 the guide also says where the
  Código UBA names plagiarism (guidelines for faculty regimes, Libro I, Título 19,
  Capítulo E; defined and sanctioned only in two postgraduate programmes of Economic
  Sciences) and why the way the inquiry's deadlines are counted (working or calendar days)
  is still open: the Ley 19.549 counts working days but does not name the universities.
- Procedures guide for Mexico (`docs/procedimientos-mx.md`, English in
  `docs/en/procedures-mx.md`). There is no national student-discipline law: each autonomous
  university sets its own (Constitution art. 3.VII; Ley General de Educación Superior
  art. 2). UNAM is the worked example: offences and sanctions (Estatuto General
  arts. 93, 97, 98, 101; on 2026-11-10 also the articles that touch academic dishonesty
  without naming plagiarism: 5, 7, 87.V, 95.VII, 96.III, in the text reformed on
  2025-03-31) and the stages and deadlines before the Tribunal Universitario
  (Reglamento arts. 2, 3, 14-14 bis, 17-20, 23, 25, 29, 31, 32, as amended on 2025-11-27).
  Amparo: Ley de Amparo arts. 5.II, 17, 18 and 61.XX. Each quote checked in the official
  text on 2026-11-08.
- Procedures guide (`docs/procedimientos.md`, English in `docs/en/procedures.md`): the
  stages and deadlines of the disciplinary procedure in Spain (Ley 3/2022 arts. 11, 12, 14,
  17-19; Ley 39/2015; Estatuto del Estudiante, arts. 7, 25, 46) and the seven minimum
  due-process guarantees in Colombia (Constitutional Court rulings T-087/20 and T-290/23),
  each quote checked in the official text on 2026-11-08. It notes that the 1954 discipline
  regulation has been repealed since 2022-02-26.
- Sukima Labs brand (marca v1.1), kept minimal: the favicon is the Sukima isotype, the
  page header carries the isotype and a link to https://sukima-labs.github.io/, the footer
  says it is a Sukima Labs project, and `web/style.css` has the brand colour tokens.
  Descargo keeps its own name, accent colour and link-preview card.
- Link previews: the web page has Open Graph and Twitter card tags and a 1200×630 picture
  (`web/og.jpg`, rendered from `scripts/og-card.html`), so shared links show a card.
- Jurisdiction packs for Argentina (`ar`: Ley 25.326 and Decreto 1558/2001), Chile (`cl`:
  Ley 19.628 until 30-11-2026 and its text rewritten by Ley 21.719 from 01-12-2026), Mexico
  (`mx`: the 2025 LGPDPPSO for public institutions and LFPDPPP for private ones) and Peru
  (`pe`: Ley 29733 and its 2024 Reglamento). Every quote was checked against the official
  text on 2026-11-05. Chile: a bill to postpone Ley 21.719 to 01-12-2027 was before the
  Chamber of Deputies on that date; recheck before 01-12-2026.
- The user guides in `docs/` are in Spanish; the English ones are in `docs/en/`.
- `descargo profile list | show | validate | unverified`: institution profiles with
  every fact's source URL, effective date and verification status. Bundled profiles:
  Universidad de Alcalá (`es/uah`), The University of Texas at Austin (`us/utexas`) and
  Universidad Católica Luis Amigó (`co/luisamigo`).
- `descargo access-request`: drafts a request for access to the detector report, in
  Markdown and PDF, from jurisdiction packs for the EU (GDPR Art. 15), Spain, the United
  Kingdom (UK GDPR), the United States (FERPA) and Colombia (Ley 1581 de 2012). Nothing is
  sent. `--institution` with `--jurisdiction` drafts a generic letter for an institution
  with no profile.
- `descargo import-report`: reads a downloaded Turnitin Similarity Report PDF (classic
  Feedback Studio layout and enhanced layout, in English and Spanish, with its
  integrity flags), a Turnitin AI Writing Report PDF (in English and Spanish, on its own or
  after the Similarity Report, with the passages it highlights as AI and its "*%" result
  under the 20 % threshold) or a Compilatio analysis report or
  certificate PDF (Magister until 2025 and Magister+ from 2026, in Spanish, with its AI
  result and the passages it attributes to AI) into the common report format, and drops the
  author or depositor name shown on it. For Magister+ it also records which results count
  in the suspicious-text percentage; for Magister, which ones the report marks "(ignorado)".
- `descargo audit`: recomputes a similarity percentage after discounting quoted and
  cited passages, the reference list, institution template text and declared own earlier
  work, explains every discount, and compares the result with the institution's published
  threshold. Reads `.docx`, `.odt`, `.pdf`, `.txt` and `.md` documents. When the report has
  an AI-writing result, the audit states it as the tool's, with the flagged passages,
  without recomputing it; a report with only an AI-writing result gets that statement
  alone, titled "AI writing result".
- `descargo inspect`: lists invisible or unusual characters, metadata, tracked changes,
  comments and hidden text in `.docx`, `.odt`, `.pdf`, `.txt` and `.md` files, with what
  each item usually means. It never changes the file and gives no score.
- An in-browser version: `descargo inspect`, `audit` and `access-request` (with a form
  instead of the YAML file) run in the browser through Pyodide, in English and Spanish,
  with Markdown, PDF and JSON downloads, an introduction to what the tool does and does not
  do, and a feedback form that prepares a message for the student to send themselves. No server receives anything, and the page may
  request only its own files. Built with `scripts/build_web.py`, served for testing with
  `scripts/serve_web.py`. See [`docs/web.md`](docs/web.md).
- Common report format `report_schema` v0.1, with published JSON Schemas for reports,
  profiles and jurisdiction packs in `schemas/`.
- English and Spanish messages and reports (`--lang`, `DESCARGO_LANG`).
- Command-line conventions shared by every command: an output file is never written over
  an input file, an existing file only with `--force`; exit status 0, 1 for refusals and
  unreadable inputs, 2 for usage errors. See [`docs/cli.md`](docs/cli.md).
- Architecture decision records 001 to 007 in [`docs/adr/`](docs/adr/).

### Fixed

- Chile pack: the bill that would postpone Ley 21.719 (Boletín 18.623-07) now moves it to
  15 October 2027, not 1 December 2027 (the Senate's text of 2026-10-28, checked
  2026-11-08). It is still in the Chamber of Deputies, so the 1 December 2026 date stands.
- The web page no longer shows empty headings when its texts fail to load, for example
  on a first visit while GitHub Pages is publishing. It checks the answer, tries once more
  and, if that fails too, says so in Spanish and English.

### Changed

- The web page names its canonical URL (`<link rel="canonical">`), the same as its
  `og:url`, so search engines index https://sukima-labs.github.io/descargo/. Both
  languages share that URL.
- Procedure guide, Peru: a second example, the UNMSM (a public university), from its
  student disciplinary regulation of 2012 and the 2025 provision that keeps it in force:
  plagiarism is an offence, five working days for the defence and fifteen to appeal. The
  PUCP example now cites the text the PUCP publishes (version 2020-006), whose only change
  is art. 11. Two "to verify" items are gone; what the UNMSM's 2025 Tribunal de Honor
  regulation changes stays open, because its annex is not published.
- Procedure guide, Colombia: it now cites the Ley 30 of 1992 (its current text from the
  Senate and the original from the Ministry of Education, read on 2026-11-10). The law
  sets no disciplinary procedure; it requires every institution to have student
  regulations with a disciplinary regime (art. 109), so the procedure comes from the
  university's own regulations. The "to verify" item on that law is gone.
- The web page can be served by hosts that cannot send headers, such as GitHub Pages. Its
  worker now starts from a `blob:` URL, so the page's `<meta>` Content-Security-Policy
  covers Pyodide too, and a file can reach only the site it came from. A workflow publishes
  the page at https://sukima-labs.github.io/descargo/.
- Spanish first: the web page opens in Spanish unless you chose English or your browser
  asks for it, and the README is in Spanish (`README.en.md` keeps the English one). The
  tagline is now «Prueba de autoría» (*Proof of authorship*).
- The project is now called **Descargo** (it was DraftWitness until 2026-11-05) and puts
  Spanish speakers first. The package and the command are now `descargo`. The schema
  identifiers (`urn:draftwitness:schema:*:0.1`) and the `draftwitness_version` field keep
  their names, so reports and profiles you have already saved stay valid; they change with
  the next schema version. The web page keeps the language you chose under the old name.
- What an import could not read (the adapters' notes) is now written in the interface
  language, so the Spanish web page and CLI show it in Spanish.
- Nine more facts checked against their official sources on 2026-10-27 and marked
  verified: the UAH coexistence rules (art. 15.3.a), UT Austin's FERPA contact, 34 CFR
  §§ 99.20-99.22, UK Data Protection Act 2018 Sch. 2 para. 25, and the data protection
  authorities for the EU, Spain, the UK (the Information Commission) and Colombia, and the
  AI Act entry, including its postponement by Regulation (EU) 2026/1744.
