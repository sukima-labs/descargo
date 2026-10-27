# ADR 003: Technology stack and repository layout

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

The tool must run on students' own machines (Windows, macOS, Linux), be auditable by
non-specialists, and, per ADR 001, also run inside a browser through Pyodide. Contributors
will often be students and researchers rather than professional developers.

## Decisions

### Language and tooling

| Concern | Choice | Why |
|---|---|---|
| Language | Python ≥ 3.12 | Readable, strong document-parsing ecosystem, runs in Pyodide |
| Environment and locking | uv, `uv.lock` committed | Fast, reproducible, one tool |
| Build backend | hatchling | Simple, supports including data folders in the wheel |
| Lint and format | ruff | One fast tool |
| Types | mypy `--strict` | Catches schema drift early |
| Tests | pytest, pytest-cov (≥ 85 %), pytest-socket | Socket blocking enforces ADR 001 |
| CLI | Typer | Typed, generates help, easy to test |

### Runtime libraries

Every **runtime** dependency must be pure Python or prebuilt in Pyodide. The CLI layer
(Typer) is the only part that the browser build does not import.

| Need | Library | Notes |
|---|---|---|
| Models and JSON Schema | pydantic v2 | Models are the source of truth; schemas are generated (ADR 004) |
| Profiles and packs | PyYAML (`safe_load` only) | Never `yaml.load` |
| Templates | Jinja2 `SandboxedEnvironment` | Templates are data a contributor can write; sandboxing limits what they can do |
| PDF output | fpdf2 with a bundled OFL-licensed font (Liberation Serif) | Pure Python; no system libraries (rules out WeasyPrint) and no LaTeX (rules out pandoc → PDF) |
| PDF input | pypdf | Pure Python |
| DOCX / ODT input | `zipfile` + defusedxml | Both formats are ZIP + XML; defusedxml blocks XML bombs and external entities |

### Internationalisation

UI strings live in one TOML catalog per locale (`locales/en.toml`, `locales/es.toml`), read
with the standard library's `tomllib`, with English as the fallback. A test checks that every
locale has every key. Generated **documents** are not translated string by string: each
jurisdiction pack ships a full template per language, because legal letters do not translate
word for word.

GNU gettext was considered. It needs a compile step for `.mo` files or Babel at runtime, and
Babel's locale data is heavy for a browser build. The TOML catalog can be converted to
gettext later if translators ask for it.

### Layout

A single Python distribution, `draftwitness`. Splitting it into a uv workspace with several
packages adds release overhead and buys nothing until other projects want to depend on
`core` alone.

```text
src/draftwitness/{core,adapters,modules/pre,modules/post,cli}   code
profiles/  jurisdictions/  schemas/                              data, at the repo root
```

The data folders live at the repository root so that contributors who do not write Python
can find and edit them. They are copied into the wheel at build time and read through
`importlib.resources`. Users can also point the CLI at their own folders (for example
`--profiles-dir`) to use a profile that has not been merged yet.

### Versioning

The package follows SemVer. Each schema (report, profile) has its own version, independent of
the package version (ADR 004).

## Consequences

- C-extension libraries that Pyodide does not ship (for example PyMuPDF) are not allowed as
  runtime dependencies. They may be used in tests or optional extras that the browser build
  does not need.
- Pinning GitHub Actions: `astral-sh/setup-uv` publishes no moving major tags, so CI pins it
  to an exact commit.
