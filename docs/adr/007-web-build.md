# ADR 007: Static in-browser build

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

ADR 001 chose a local CLI plus a static in-browser build: the same Python package, run in
the student's browser through Pyodide, served as static files that never receive documents
or results. The first testers (students in Colombia) are not all comfortable with a
terminal, so the browser build is how most of them will use Descargo. This ADR records
how that build is made, loaded, hosted and tested.

## Options

### Where Pyodide comes from

1. **The jsDelivr CDN**, as Pyodide's documentation suggests. Nothing to host, but every
   visit tells a third party the student's IP address and when they used the tool, the page
   depends on that third party being up and honest, and the Content Security Policy would
   have to allow another origin.
2. **Self-hosted**: the build copies Pyodide and every wheel next to the page. About 20 MB
   to host, and the site can forbid every other origin.

### How packages are installed

1. **micropip**, resolving from PyPI at run time: network requests from the student's
   browser, and versions chosen when the page loads, not when it was built.
2. **A trimmed `pyodide-lock.json`** listing only the packages Descargo needs, each with
   its SHA-256, loaded with `pyodide.loadPackage("descargo")`: no resolver, no PyPI, and
   Pyodide checks each file's integrity as it loads it.

### Where Python runs

1. **On the page's main thread**: simplest, but the page freezes while Python works.
2. **In a Web Worker**: the page stays responsive; files pass to the worker as bytes.

## Decision

Self-hosted Pyodide, a trimmed lock file, and a Web Worker.

- **Pyodide 314.0.7** (Python 3.14), pinned with the SHA-256 of its `pyodide-core` release
  tarball. Compiled packages (pydantic-core, PyYAML, regex, MarkupSafe, Pillow) and the
  pure packages Pyodide ships come from Pyodide's own build, checked against the hashes in
  its lock file. Pure Python wheels Pyodide does not ship (pypdf, fpdf2, defusedxml) come
  from PyPI, checked against the hashes in `uv.lock`. The Descargo wheel is built from
  the checkout. `scripts/build_web.py` does all of this, and is the only code that uses the
  network; it runs at build time, never in the student's browser.
- **The CLI layer is not installed.** Typer is left out of the browser build, as ADR 003
  foresaw. The page calls `descargo.web`, a thin module that calls the same functions
  as the CLI and returns JSON.
- **Files stay in the tab.** The page reads the chosen files, hands the bytes to the
  worker, which writes them to Pyodide's in-memory file system in a fresh folder and deletes
  it when the action ends. Form details are never written to browser storage; only the
  interface language is remembered.
- **No HTML from data.** Results are Markdown split into blocks by the same parser the PDF
  renderer uses (`markdown_blocks`), and the page draws them with `textContent`. Nothing
  from a student's file, a report or a profile can inject markup.
- **Content Security Policy:** `default-src 'none'; script-src 'self' 'wasm-unsafe-eval';
  worker-src 'self'; connect-src 'self'; style-src 'self'; img-src 'self'; form-action
  'none'; base-uri 'none'`, plus `frame-ancestors 'none'` in the header. Pyodide needs only
  `'wasm-unsafe-eval'`, not `'unsafe-eval'` (checked in Chromium with the policy as a
  header). The page carries the policy in a `<meta>` tag, but a `<meta>` policy does not
  cover the worker, so the host must also send it as an HTTP header.
- **Hosting:** any static host that can send that header and keeps no more logs than it
  needs. `scripts/serve_web.py` is the reference: standard-library HTTP server, policy and
  other security headers, no access log, no directory listings, listening on 127.0.0.1 behind
  Tailscale Serve or Funnel (or any reverse proxy). Serving the site publishes the
  Descargo wheel, so a public URL is the maintainer's decision while the repository is
  private.
- **Verifiable:** the build writes `build.json` (Descargo version, commit, Pyodide
  version), shown in the page footer, and `SHA256SUMS` for every file.
- **Features:** the inspector, the similarity audit (which also offers the report as
  Descargo JSON, what `import-report` writes) and the access-request letter, in English
  and Spanish, with Markdown, PDF and JSON downloads. Profile validation and listing of
  unverified facts stay in the CLI, for contributors.

## Testing

- `tests/test_web_api.py` tests `descargo.web` under CPython, including that it does not
  import the CLI.
- `tests/web/smoke.mjs` loads the built site's own Pyodide in Node, with `fetch` disabled,
  and runs the inspector, the audit, the letter and the PDF renderer on synthetic fixtures.
  CI builds the site and runs it on every push (job `web`).
- Before a release, a person opens the page in a real browser and checks that the console
  shows no policy violations and that the network panel shows requests to the site only.

## Consequences

- The first visit downloads about 20 MB; browsers cache it afterwards.
- The browser runs Pyodide's versions of the compiled packages, which can differ from the
  CLI's (for example Pillow 12 against 13). The smoke test catches breakage; the minimum
  versions in `pyproject.toml` must stay at or below Pyodide's.
- A runtime dependency that is neither pure Python nor shipped by Pyodide breaks the build
  (`build_web.py` refuses it), which enforces ADR 003.
- Templates in a declarations file must be given inline (`text:`) or as a report source in
  the browser, because the page cannot read a second file the declarations point to.
- Upgrading Pyodide means changing two pinned values in `build_web.py` and rerunning the
  smoke test.
