# AGENTS.md

Instructions for coding agents working on Descargo. Humans: start with
[README.en.md](README.en.md) and [CONTRIBUTING.md](CONTRIBUTING.md); this file follows the
[AGENTS.md](https://agents.md) convention and does not replace them.

## Project overview

Descargo is a local-first evidence toolkit for students facing plagiarism and AI-detector
false positives. It runs as a CLI (`descargo`) and, unchanged, in the browser under Pyodide
(the site at https://sukimalabs.com/descargo/). Python 3.12, managed with `uv`. Pre-alpha.

- `src/descargo/` — code: `core/` (report schema, evidence), `adapters/` (detector PDFs →
  report JSON), `modules/pre/` and `modules/post/`, `cli/`, `web/` (the in-browser API).
- `web/` — the static page (HTML, JS, CSS); `scripts/build_web.py` builds it into `build/web`.
- `profiles/`, `jurisdictions/` — sourced data (YAML) and letter templates (Jinja).
- `schemas/` — generated JSON Schemas. `docs/adr/` — decisions. `tests/fixtures/` — synthetic only.

## Setup, build and test

```bash
uv sync
uv run pre-commit install
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests scripts        # strict
uv run pytest                        # sockets disabled; coverage must stay ≥ 85 %
uv run python scripts/build_web.py && node tests/web/smoke.mjs build/web   # web job of CI
```

CI (`.github/workflows/ci.yml`) runs exactly these. Run them before you call a change done
and fix what fails; the `pre-pr-check` skill lists the whole sequence.

## Hard rules

1. **No real student data, ever** — no real essay, thesis, detector report, email, name,
   student ID or screenshot, not even anonymised. The repository is public. Fixtures are
   synthetic and live next to the script that generates them in `tests/fixtures/`.
2. **No network by default.** Nothing leaves the device unless the user passes an explicit,
   documented flag. Do not add network calls to make a test pass.
3. **No evasion features**: nothing that rewrites, paraphrases or "humanises" text, predicts
   or lowers detector scores, or strips watermarks ([ADR 002](docs/adr/002-non-goals.md)).
4. **Not legal advice.** The disclaimer is added in code; templates cannot remove it and must
   not read like a lawyer's opinion.
5. **Pyodide-compatible runtime dependencies** only: pure Python or shipped by Pyodide
   ([ADR 003](docs/adr/003-stack.md), [ADR 007](docs/adr/007-web-build.md)). Anything else
   goes in an optional CLI extra; `build_web.py` refuses the rest.
6. **Facts need official sources.** Every profile or jurisdiction fact carries `source_url`,
   a short verbatim `quote` and `verification`. Mark `verified` (with `checked_on`) only after
   finding the quote in the official source yourself; otherwise `needs_verification`.
   Never cite a blog, forum or AI answer.

## Code style

- Ruff (lint + format) and `mypy --strict` are the style; `.editorconfig` covers the rest.
- User-facing strings go through the i18n layer (English and Spanish); docs exist in
  Spanish (`docs/`) and English (`docs/en/`) — update both.
- Non-obvious design decision → write an ADR in `docs/adr/` (options, consequences,
  recommendation) **before** implementing it.

## Commits and pull requests

- [Conventional Commits](https://www.conventionalcommits.org/) (`feat(post): …`,
  `fix(adapters): …`, `docs(adr): …`, `test: …`, `chore: …`); one logical change per
  commit, tests in the same commit as the code.
- A line under **Unreleased** in `CHANGELOG.md` for every change a user would notice.
- Work on a branch and open a PR; merge only with CI green.
- No personal names or student details in commit messages, and no AI-tool attribution
  trailers.

## Agent skills

Task-specific procedures live as [Agent Skills](https://agentskills.io/specification) in
`.claude/skills/<name>/SKILL.md`; read the one that matches the task:

| Skill | Use it when |
|---|---|
| `pre-pr-check` | before committing or opening a PR: the full local CI sequence |
| `institution-profile` | adding or updating `profiles/<country>/<institution>.yaml` |
| `jurisdiction-pack` | adding a country pack, a legal basis or a letter language |
