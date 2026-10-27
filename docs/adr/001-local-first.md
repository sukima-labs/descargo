# ADR 001: Local-first, no backend

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

DraftWitness handles some of the most sensitive material a student has: unpublished work,
detector reports that may accuse them of misconduct, and letters to their university. Its
value as a defense tool depends on two things: students trusting it with that material, and
third parties (instructors, appeal panels, ombudspersons) trusting the evidence it produces.

A hosted service would hold a corpus of accused students' work. That corpus is a breach
waiting to happen, a target for subpoenas and data-access requests, and a conflict of
interest: whoever runs it could be pressured by institutions or vendors. It would also make
the evidence depend on trusting the operator.

There is also a practical need: early testers (students in Colombia, recruited through a
friend of the maintainer) are not all comfortable with a terminal, so the tool must reach
them without a server-side install.

## Options

1. **Hosted web service.** Easiest for students; violates every concern above.
2. **Local CLI / desktop app only.** Fully private; hard for non-technical students.
3. **Local CLI plus a static in-browser build.** The same Python package runs in the
   student's browser through Pyodide (WebAssembly). The host serves static files only and
   never receives documents or results.

## Decision

Option 3.

- **No backend of our own.** No server receives, stores or processes student data. No
  accounts, telemetry, analytics, crash reporting or "phone home" update checks.
- **Static hosting is allowed** because it serves code, not data. During testing the static
  build is served from the development container through Tailscale Funnel; later through any
  static host. The page must ship a Content Security Policy that forbids network requests
  other than fetching its own static assets, and the host must not log more than it needs to
  serve files.
- **Network calls are opt-in.** A function may contact the network only when the user passes
  an explicit flag for that specific purpose, and every such call is listed in
  `docs/network.md` (purpose, endpoint, data sent). Foreseen uses: RFC 3161 or
  OpenTimestamps time-stamping of evidence hashes (only the hash is sent), and downloading
  public regulations or profile updates (nothing about the student is sent).
- **Nothing is sent to the institution.** DraftWitness prepares documents; the student
  decides whether and how to send them.

## Enforcement

- The test suite runs with sockets disabled (`pytest-socket`); importing any module must not
  open a socket.
- When network features arrive, all network I/O goes through a single module so it can be
  audited and tested, and each feature has a test that it is off by default.
- Review rule: a pull request that adds a network call without a flag and a `docs/network.md`
  entry is rejected.

## Consequences

- No running cost and no data liability for the project.
- We cannot offer features that need a shared corpus (e.g. comparing against a detector's
  database). That is acceptable: the student already holds the report.
- Profile and jurisdiction data ship with releases, so they can go stale; every data point
  carries an effective date and source so the student can check it.
- Runtime dependencies must work under Pyodide (see ADR 003).
