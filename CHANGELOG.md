# Changelog

All notable changes to DraftWitness are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Before 1.0, any minor version
may break the command line, the profile format or the report format.

## [Unreleased]

Nothing has been released yet. Phase 1 is in progress; the package version is
`0.1.0.dev0`.

### Added

- `draftwitness profile list | show | validate | unverified`: institution profiles with
  every fact's source URL, effective date and verification status. Bundled profiles:
  Universidad de Alcalá (`es/uah`), The University of Texas at Austin (`us/utexas`) and
  Universidad Católica Luis Amigó (`co/luisamigo`).
- `draftwitness access-request`: drafts a request for access to the detector report, in
  Markdown and PDF, from jurisdiction packs for the EU (GDPR Art. 15), Spain, the United
  Kingdom (UK GDPR), the United States (FERPA) and Colombia (Ley 1581 de 2012). Nothing is
  sent. `--institution` with `--jurisdiction` drafts a generic letter for an institution
  with no profile.
- `draftwitness import-report`: reads a downloaded Turnitin Similarity Report PDF (classic
  Feedback Studio layout in English; enhanced layout in English and Spanish, with its
  integrity flags), a Turnitin AI Writing Report PDF (in English and Spanish, on its own or
  after the Similarity Report, with the passages it highlights as AI and its "*%" result
  under the 20 % threshold) or a Compilatio analysis report or
  certificate PDF (Magister until 2025 and Magister+ from 2026, in Spanish, with its AI
  result and the passages it attributes to AI) into the common report format, and drops the
  author or depositor name shown on it. For Magister+ it also records which results count
  in the suspicious-text percentage; for Magister, which ones the report marks "(ignorado)".
- `draftwitness audit`: recomputes a similarity percentage after discounting quoted and
  cited passages, the reference list, institution template text and declared own earlier
  work, explains every discount, and compares the result with the institution's published
  threshold. Reads `.docx`, `.odt`, `.pdf`, `.txt` and `.md` documents. When the report has
  an AI-writing result, the audit states it as the tool's, with the flagged passages,
  without recomputing it; a report with only an AI-writing result gets that statement
  alone, titled "AI writing result".
- `draftwitness inspect`: lists invisible or unusual characters, metadata, tracked changes,
  comments and hidden text in `.docx`, `.odt`, `.pdf`, `.txt` and `.md` files, with what
  each item usually means. It never changes the file and gives no score.
- An in-browser version: `draftwitness inspect`, `audit` and `access-request` (with a form
  instead of the YAML file) run in the browser through Pyodide, in English and Spanish,
  with Markdown, PDF and JSON downloads, an introduction to what the tool does and does not
  do, and a feedback form that prepares a message for the student to send themselves. No server receives anything, and the page may
  request only its own files. Built with `scripts/build_web.py`, served for testing with
  `scripts/serve_web.py`. See [`docs/web.md`](docs/web.md).
- Common report format `report_schema` v0.1, with published JSON Schemas for reports,
  profiles and jurisdiction packs in `schemas/`.
- English and Spanish messages and reports (`--lang`, `DRAFTWITNESS_LANG`).
- Command-line conventions shared by every command: an output file is never written over
  an input file, an existing file only with `--force`; exit status 0, 1 for refusals and
  unreadable inputs, 2 for usage errors. See [`docs/cli.md`](docs/cli.md).
- Architecture decision records 001 to 007 in [`docs/adr/`](docs/adr/).

### Changed

- Nine more facts checked against their official sources on 2026-10-27 and marked
  verified: the UAH coexistence rules (art. 15.3.a), UT Austin's FERPA contact, 34 CFR
  §§ 99.20-99.22, UK Data Protection Act 2018 Sch. 2 para. 25, and the data protection
  authorities for the EU, Spain, the UK (the Information Commission) and Colombia, and the
  AI Act entry, including its postponement by Regulation (EU) 2026/1744.
