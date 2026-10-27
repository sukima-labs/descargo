# Contributing to DraftWitness

Thank you for helping students defend their own work. Please read this whole file first.

## Ground rules

1. **No real student data, ever.** Never commit a real essay, thesis, detector report,
   email, name, student ID or screenshot, not even anonymised. Fixtures are synthetic and
   live in `tests/fixtures/`, next to the script that generates them. Work with real files
   outside the repository (or under the git-ignored `local/` folder).
2. **No network by default.** No function may send data off the device unless the user
   passes an explicit flag, and that call must be documented. The test suite runs with
   sockets disabled (`pytest-socket`); a test that needs the network is a design smell.
3. **No evasion features.** Pull requests that rewrite, paraphrase or "humanise" text, try
   to predict or lower detector scores, or strip watermarks will be closed. See
   [ADR 002](docs/adr/002-non-goals.md).
4. **Not legal advice.** Every generated document carries the disclaimer, and code enforces
   it. Do not word templates as if they were a lawyer's opinion.

## Development setup

```bash
uv sync
uv run pre-commit install
uv run pytest
```

CI runs `ruff check`, `ruff format --check`, `mypy --strict` and `pytest` (coverage ≥ 85 %).
Runtime dependencies must also work under Pyodide, because a static in-browser build is
planned (see [ADR 003](docs/adr/003-stack.md)).

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(post): …`,
  `fix(adapters): …`, `docs(adr): …`, `test: …`, `chore: …`.
- One logical change per commit; tests in the same commit as the code.
- If a design decision is not obvious, write an ADR in `docs/adr/` (options, consequences,
  recommendation) **before** implementing it.

## Adding or updating data

Institution profiles (`profiles/`) and jurisdiction packs (`jurisdictions/`) are data, and
data needs sources:

- every data point carries `source_url`, `effective_date` and a verification status;
- mark anything you have not personally checked against an **official** source
  (the university's own site, an official gazette, a regulator) as `needs_verification`;
- never cite a blog, forum or AI answer as the source of a legal or policy fact.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
