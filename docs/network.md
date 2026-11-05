# Network calls

Descargo makes **no network calls** unless you pass an explicit flag for a specific
purpose ([ADR 001](adr/001-local-first.md)). This file lists every such call.

| Feature | Flag | Endpoint | Data sent |
|---|---|---|---|
| *(none in this version)* | | | |

The in-browser version requests only its own files from the site that serves it; its
Content Security Policy forbids any other request ([ADR 007](adr/007-web-build.md)).
Building that version (`scripts/build_web.py`) downloads Pyodide from GitHub and jsDelivr
and three wheels from PyPI, each checked against a pinned SHA-256. That happens on the
developer's machine at build time, never on the student's device.
