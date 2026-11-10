# ADR 010: A marketing module that is documentation, not code

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

Descargo has a working pre-alpha, a public repository and six country guides, but almost no
audience: on 2026-11-11 the repository had 1 star, 0 forks and 1 unique visit in 14 days. The
maintainer asked for a promotion module and a plan to carry it out. The constraints already
in force are ADR 001 (no telemetry, nothing leaves the device), ADR 002 (no evasion), the
rule that the repository is public (everything pushed is published) and the rule that no real
student data is ever stored.

## Options

1. **A module inside `src/descargo/`** (for example, a tracker or a share button that
   measures use). Rejected: it would add telemetry or a backend, which ADR 001 rules out.
2. **A separate private repository.** Keeps contacts safe but hides the rules the promotion
   must follow from the people who contribute, and splits the shared GitHub channel.
3. **A `marketing/` folder of Markdown in this repository**, with a private vault note for
   anything personal.

## Decision

Option 3. `marketing/` holds the analysis, the plan, the messages (every figure with its
source and reading date), the guardrails, the channels, the measurement method and drafts. It
contains no code that runs in the product and no data about people.

- Public, because the rules a promotion must obey (no evasion, no legal advice, no student
  data, say who is speaking) are credibility assets and contributors should see them.
- Contact lists, mailbox details and analytics exports stay out of the repository, in the
  maintainer's private notes.
- Measurement uses only public GitHub figures, Search Console (managed outside this
  repository) and what students choose to send; the web page gets no analytics.
- Actions outside the repository are logged in `marketing/REGISTRO.md`, and the first
  publication in each channel needs the maintainer's approval of the exact text.

## Consequences

- The promotion cannot measure users, only public signals. That is accepted.
- Drafts live in a public repository, so they must be written as if already published.
- Facts in `marketing/MENSAJES.md` expire and must be re-read before reuse.
