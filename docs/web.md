# The in-browser version

Descargo also runs as a web page: the same Python code, in your browser, through
[Pyodide](https://pyodide.org/). There is no server behind it. The page is a set of
static files; your files and details stay inside the browser tab and are gone when you close
or reload it. See [ADR 007](adr/007-web-build.md).

It offers three of the CLI's commands, in English and Spanish:

| Tab | Same as |
|---|---|
| Before you submit | `descargo inspect` |
| Check a detector report | `descargo audit` (and `import-report`: download the report as JSON) |
| Ask for the report | `descargo access-request`, with a form instead of the YAML file; "not listed" options per country draft the generic letter (`--institution`) |
| Send feedback | no CLI equivalent: a short form that prepares a message for the student to copy or open in their own e-mail |

Above the tabs, a short introduction says what Descargo is, how to use it, which reports
it reads today, what it does not do, and that this is a test version.

The feedback form needs no Python, so it works even when the page fails to load. Nothing is
sent: the student sees the whole message, which carries only what they wrote, the page's
version and language, and, if they tick the box, the page's last status message. With no
address set, the page asks them to send it to whoever shared the page; set `FEEDBACK_EMAIL`
in `web/app.js` to offer an "Open in my e-mail" link (`mailto:`) as well.

Every result can be downloaded as Markdown and PDF (the same PDF the CLI writes), and the
inspection and audit also as JSON.

## Build it

```bash
uv run python scripts/build_web.py          # writes build/web/ (about 20 MB)
node tests/web/smoke.mjs build/web          # runs Descargo in that Pyodide (Node 18+)
```

The build downloads Pyodide and the wheels the browser needs, checks each file against a
pinned SHA-256 (Pyodide's release tarball, Pyodide's lock file, and `uv.lock`), and caches
the downloads in `.cache/web/`. It is the only step that uses the network; the built site
requests nothing but its own files.

`build/web/build.json` records the Descargo version, the commit and the Pyodide version,
and the page shows them in its footer. `build/web/SHA256SUMS` lists every file's hash, so
anyone can check that a deployed copy matches a build.

## Serve it

```bash
uv run python scripts/serve_web.py          # http://127.0.0.1:8040/
```

The development server sends the security headers and keeps no access log. Any static host
works, including those that cannot send headers, such as GitHub Pages, where the public page
lives (`https://sukima-labs.github.io/descargo/`). The page carries its
`Content-Security-Policy` in a `<meta>` tag, and the Web Worker where Python runs starts from
a `blob:` URL, which inherits that policy, so a file can reach only the site it came from.
Opening `index.html` from disk does not work,
because browsers do not start module workers from `file://` URLs.

## Limits

- The first visit downloads about 20 MB; later visits use the browser's cache.
- In a declarations file, give each template's text inline (`text:`) or name the report
  source (`source:`): the page cannot open a second file that `file:` points to.
- Only the bundled institution profiles are available; `--profiles-dir` has no equivalent.
- Profile validation and the list of unverified facts stay in the CLI.
