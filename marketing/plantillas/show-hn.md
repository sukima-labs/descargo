# Show HN (draft in English, not posted)

**Title:** Show HN: Descargo, a local, no-evasion toolkit for students flagged by AI/plagiarism detectors

I'm the developer, so this is self-promotion.

Descargo helps students whose own work is flagged by a plagiarism or AI detector. It runs in
the browser (Pyodide); files never leave the device, with no accounts or analytics. It:
inspects a file for invisible characters and metadata before submission, reads Turnitin,
Compilatio and Copyleaks reports and explains what the similarity score includes, drafts a
data-access request under the student's country's law, and has procedure guides for Spain,
Colombia, Mexico, Argentina, Chile and Peru with sources and verification dates.

What it deliberately does not do: rewrite or "humanize" text, predict or lower detector
scores, or strip watermarks (ADR 002). The point is evidence a panel can trust.

It's pre-alpha, Spanish-first, AGPL-3.0, and some guides still have unverified points that
are marked as such. Feedback on the architecture and on the legal guides is welcome.

Web: https://sukimalabs.com/descargo/ · Code: https://github.com/sukima-labs/descargo
