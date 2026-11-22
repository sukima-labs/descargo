---
name: pre-pr-check
description: Runs Descargo's full local CI sequence (ruff lint and format, mypy strict, pytest with coverage, in-browser Pyodide build and smoke test) and the pull-request checklist (changelog, both doc languages, no real data). Use before committing, opening or merging a pull request, or when the user asks whether a change is ready.
license: AGPL-3.0-or-later
compatibility: Requires uv, Python 3.12+, Node.js and internet access for the first web build (it downloads Pyodide).
metadata:
  project: descargo
---

# Pre-PR check

Run from the repository root, in this order; stop at the first failure, fix it, rerun.

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .        # fix with: uv run ruff format .
uv run mypy src tests scripts
uv run pytest                       # sockets disabled; coverage ≥ 85 %
uv run python scripts/build_web.py  # only if src/, web/, scripts/ or dependencies changed
node tests/web/smoke.mjs build/web
```

The web build caches downloads in `.cache/` (git-ignored); later builds work offline. It
fails on any runtime dependency Pyodide cannot load: move that dependency to an optional
CLI extra instead of loosening the check.

## Checklist before the PR

- [ ] One logical change; Conventional Commit message, no personal names, no AI attribution.
- [ ] Tests in the same commit as the code; no network, no real student material.
- [ ] `CHANGELOG.md` → **Unreleased** has a line if a user would notice the change.
- [ ] Docs changed in both `docs/` (Spanish) and `docs/en/` (English), and README.md /
      README.en.md together.
- [ ] A non-obvious decision has its ADR in `docs/adr/`.
- [ ] `git status` shows nothing from `local/`, `*.real.pdf` or `*.real.docx`.

## Merging

`gh pr checks <n>` must list checks **and** all of them green before `gh pr merge`. Never
chain `gh pr checks --watch && gh pr merge`: with no checks registered yet, the watch exits
0 and the merge goes through untested.
