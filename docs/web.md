# The in-browser version

DraftWitness also runs as a web page: the same Python code, in your browser, through
[Pyodide](https://pyodide.org/). There is no server behind it. The page is a set of
static files; your files and details stay inside the browser tab and are gone when you close
or reload it. See [ADR 007](adr/007-web-build.md).

It offers three of the CLI's commands, in English and Spanish:

| Tab | Same as |
|---|---|
| Before you submit | `draftwitness inspect` |
| Check a similarity report | `draftwitness audit` (and `import-report`: download the report as JSON) |
| Ask for the report | `draftwitness access-request`, with a form instead of the YAML file |

Every result can be downloaded as Markdown and PDF (the same PDF the CLI writes), and the
inspection and audit also as JSON.

## Build it

```bash
uv run python scripts/build_web.py          # writes build/web/ (about 20 MB)
node tests/web/smoke.mjs build/web          # runs DraftWitness in that Pyodide (Node 18+)
```

The build downloads Pyodide and the wheels the browser needs, checks each file against a
pinned SHA-256 (Pyodide's release tarball, Pyodide's lock file, and `uv.lock`), and caches
the downloads in `.cache/web/`. It is the only step that uses the network; the built site
requests nothing but its own files.

`build/web/build.json` records the DraftWitness version, the commit and the Pyodide version,
and the page shows them in its footer. `build/web/SHA256SUMS` lists every file's hash, so
anyone can check that a deployed copy matches a build.

## Serve it

```bash
uv run python scripts/serve_web.py          # http://127.0.0.1:8040/
```

The development server sends the headers the site needs and keeps no access log. Any other
static host works if it sends the same `Content-Security-Policy` header (copy it from
`scripts/serve_web.py`): the page also carries the policy in a `<meta>` tag, but that tag does
not cover the Web Worker where Python runs. Opening `index.html` from disk does not work,
because browsers do not start module workers from `file://` URLs.

## Limits

- The first visit downloads about 20 MB; later visits use the browser's cache.
- In a declarations file, give each template's text inline (`text:`) or name the report
  source (`source:`): the page cannot open a second file that `file:` points to.
- Only the bundled institution profiles are available; `--profiles-dir` has no equivalent.
- Profile validation and the list of unverified facts stay in the CLI.
