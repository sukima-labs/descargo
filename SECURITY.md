# Security policy

Descargo handles sensitive material on the student's own device: their work, detector
reports, and documents addressed to their university. We treat these classes of bug as
security issues:

- any path that sends data off the device without an explicit user flag;
- any way for a crafted input (PDF, DOCX, ODT, HTML, YAML profile, template) to execute
  code, read files outside what the user selected, or exhaust resources;
- any way for Descargo to modify a file the user only asked it to inspect;
- weaknesses in evidence signing, hashing, time-stamping or verification (phase 2);
- a generated document that omits the "not legal advice" disclaimer.

## Reporting a vulnerability

Please **do not** open a public issue. While the repository is private, report privately to
the maintainers through GitHub (a direct message to the repository owner). A dedicated
security contact and GitHub private vulnerability reporting will be enabled before the first
public release.

Include the version (`descargo --version`), your OS, and a **synthetic** reproducer.
Never send us a real student's document or report.

We aim to acknowledge reports within 7 days.

## Supported versions

Only the latest release receives fixes during the 0.x series.
