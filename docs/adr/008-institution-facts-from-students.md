# ADR 008: Asking students for institution facts

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

Profiles have gaps. On 2026-10-27, `co/luisamigo` had no student regulations, and every
bundled profile had facts still marked `needs_verification`. Most testers' institutions have
no profile at all. Students are often the people with the documents a profile needs:
their student regulations, the AI policy of their course, the office that answers access
requests and how long it took.

DraftWitness is free, and the maintainer wants to use each use of it to ask students for the
missing facts. The constraints are ADR 001 (nothing leaves the device unless the student
sends it) and the maintainer's rule that **no personal data of students** is collected.

## Options

1. **A form that posts to a server.** Simplest for students, but it needs a backend, which
   ADR 001 rules out. It would receive whatever students type, including personal data we
   asked them not to give.
2. **An optional contribution panel that prepares a message the student sends themselves.**
   After a result, the page lists what is missing or unverified for the chosen institution,
   or offers to start a profile when the institution is not listed. The student can paste
   an official link, the article or section, and a short verbatim quote. The page builds a
   plain-text or YAML message and offers to copy it, or opens the student's email program
   (`mailto:`) addressed to the project. Nothing is sent unless the student sends it.
3. **Collect through the testers' coordinator** (offline, case by case). No code, but it
   does not scale and leaves no structured record.

## Decision

Option 2.

- **Institution facts only.** The panel has fields for: the institution and campus, the
  faculty or programme (as published, not the student's own), the official URL or document
  title, the article or section, a quote of up to 300 characters, and the date the student
  read it. There is no field for name, email, student ID, course group, grades or any
  description of the student's case. The panel says so, and asks the student not to
  include personal data in the quote.
- **Nothing automatic.** The message is built in the browser. The student copies it or sends
  it with their own email program. The page makes no request, so the Content Security Policy
  of ADR 007 does not change. A `mailto:` link is a navigation, not a request.
- **Every contribution is a lead, not a verification.** A maintainer checks each fact against
  the official source before it enters a profile, as today: `verified` still needs a quote
  found by a person in the official source. A contribution never changes a profile directly.
- **Opt-in and quiet.** The panel is collapsed by default, under the result. It never blocks
  or delays a result, and it never asks twice in one visit.
- **What students may report later.** The time an institution took to answer an access
  request is useful, but it describes the student's own case, so it is left out of this ADR.

## Open questions for the maintainer

- The address that receives contributions. A dedicated mailbox is recommended, not a
  personal one; SECURITY.md also needs a contact.
- Whether contributions may later arrive as GitHub issues, once the repository is public.

## Consequences

- No backend, and no personal data held by the project beyond what a student chooses to put
  in an email, and then only in the maintainer's mailbox.
- Emails may contain personal data anyway (a signature, a pasted paragraph). The
  maintainer copies only the institution facts into the repository, and deletes the email
  once it has been processed.
- Profiles grow from many sources, but the bar for `verified` does not move.
