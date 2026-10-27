# DraftWitness

**A witness for your drafts.** DraftWitness is an open-source, local-first toolkit that helps
university students defend themselves against **false positives** from plagiarism and
AI-writing detectors (Turnitin, SafeAssign, StrikePlagiarism, Compilatio, Copyleaks, GPTZero,
Originality.ai, Pangram, …). It covers coursework, essays, reports, bachelor's and master's
theses, and doctoral dissertations, in any country.

> [!IMPORTANT]
> **DraftWitness is not legal advice.** It helps you organise evidence and exercise rights
> you may already have. Laws, university regulations and deadlines change and differ by
> country, institution and case. Check the sources it cites and, when the stakes are high,
> talk to your student ombudsperson, student union or a lawyer.

## What it does (phase 1 targets, in progress)

- **Before you submit (`pre`)**: inspects your file for invisible or control Unicode
  characters and for document metadata that could raise questions, so *you* decide what to
  do. It reports; it never modifies your file.
- **After a flag (`post`)**:
  - drafts a request for access to the detector report under the law that applies to you
    (GDPR Art. 15, UK GDPR, FERPA, Colombia's Ley 1581 de 2012, …);
  - audits a similarity report, discounting properly quoted and referenced passages,
    bibliography, template text and your own declared earlier work, and explains every
    discount against your institution's published threshold.
- **Institution profiles** record each university's AI policy, similarity thresholds,
  regulations and deadlines, every data point with its source URL, effective date and
  verification status.

## What it will never do

DraftWitness provides evidence. It does **not** rewrite, paraphrase or "humanise" text, does
not predict or lower detector scores, and does not remove watermarks. See
[ADR 002](docs/adr/002-non-goals.md).

## Principles

1. **Local-first.** Everything runs on your device. No backend, no telemetry, no accounts.
   Any network call is optional, explicit and documented.
2. **Verifiable evidence.** Open formats, hashes and signatures that a third party can check
   without trusting us.
3. **Agnostic.** Anything specific to a university, detector or country lives in pluggable
   adapters, profiles and jurisdiction packs.

## Status

Pre-alpha, phase 1. Not yet usable by students. The roadmap and design decisions live in
[`docs/adr/`](docs/adr/).

## Repository layout

```text
src/draftwitness/
  core/report_schema/   common report format (versioned JSON Schema + pydantic)
  core/evidence/        writing-process evidence packages (phase 2)
  core/stylometry/      personal style baseline (phase 2)
  adapters/             detector report parsers → report_schema
  modules/pre/          checks before submission
  modules/post/         defense after a flag
  cli/                  command-line interface
profiles/               institution profiles (YAML), with sources
jurisdictions/          legal-basis packs and document templates per country/region
schemas/                generated JSON Schemas
docs/adr/               architecture decision records
docs/research/          surveys of prior art and reusable components
tests/fixtures/         synthetic fixtures only
```

## Usage (so far)

```bash
uv run draftwitness profile list
uv run draftwitness profile show es/uah --path escuela-doctorado
uv run draftwitness profile unverified          # facts a human still has to check

# Draft a request for access to the detector report (Markdown + PDF, on your device)
cp examples/student.example.yaml ~/my-details.yaml   # edit it OUTSIDE the repository
uv run draftwitness access-request --profile es/uah --student ~/my-details.yaml

# Before you submit: list invisible characters, metadata, tracked changes, hidden text…
uv run draftwitness inspect my-essay.docx

# Read a downloaded Turnitin Similarity Report (PDF) into DraftWitness JSON
uv run draftwitness import-report turnitin-report.pdf --out report.json

# Audit a similarity report: the Turnitin PDF itself, or DraftWitness JSON
uv run draftwitness audit turnitin-report.pdf --document my-essay.docx \
    --declarations ~/my-declarations.yaml --profile es/uah --format pdf --out audit.pdf
```

The inspector reports what your file contains besides its visible text and what each item
usually means; it never changes the file and gives no score. See
[`docs/inspect.md`](docs/inspect.md) and [ADR 006](docs/adr/006-pre-submission-inspector.md).

The Turnitin adapter reads the Feedback Studio and the enhanced Similarity Report PDFs, in
English, and drops the author name shown on the report. See [`docs/import.md`](docs/import.md).

The audit discounts quoted and cited passages, the reference list, institution template
text and your declared own earlier work, and explains each discount. See
[`docs/audit.md`](docs/audit.md) and [ADR 005](docs/adr/005-similarity-auditor.md).

The interface speaks English and Spanish (`--lang es`, or `DRAFTWITNESS_LANG=es`).

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync
uv run pre-commit install
uv run pytest            # runs with network sockets disabled
uv run ruff check . && uv run ruff format --check . && uv run mypy src tests
uv run draftwitness --help
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

[AGPL-3.0-or-later](LICENSE). If you run a modified version for others, including over a
network, you must offer them its source code.
