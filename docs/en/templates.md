# Writing document templates

*[Español](../templates.md) · English*

Jurisdiction packs (`jurisdictions/<id>/`) hold Jinja2 templates that Descargo renders
on the student's device. Templates run in Jinja2's **sandbox** with `StrictUndefined`: a
misspelt variable is an error, not an empty string.

## Rules

- Write the **letter only**. Descargo adds the note for the student at the top and the
  "not legal advice" footer at the bottom in code; a template cannot remove them.
- Keep the tone factual. An access request asks for information; it does not argue the case.
- Cite only provisions that are listed, with a source, in the pack's `legal_bases`.
- Use the Markdown subset the PDF renderer understands: `#` headings, paragraphs, `1.` and
  `-` lists, `**bold**`, and a trailing `\` for a line break.
- One template per language (`access_request.<lang>.md.j2`). A pack that extends another
  inherits the parent's templates for languages it does not define.

## Variables for `access_request`

| Variable | Type | Notes |
|---|---|---|
| `student.name`, `student.email` | str | always present |
| `student.student_id`, `student.identity_document`, `student.postal_address`, `student.programme` | str or none | optional |
| `request.submission_title`, `request.course` | str or none | optional |
| `request.extra_items` | list of str | number them after the standard items |
| `submission_date` | str or none | already formatted for the letter's language |
| `tools` | list of str | display names, e.g. `Turnitin`; defaults to the profile's tools |
| `institution` | str | institution name from the profile |
| `recipient` | contact or none | chosen from the profile by the pack's `recipient_roles` |
| `recipient_block` | str or none | name, address and email joined with line breaks |
| `date` | str | letter date, formatted for the language |
| `deadline` | object or none | the pack's response deadline |
| `duration(deadline)` | function | e.g. "one month", "10 días hábiles" |
| `localized(text)` | function | picks the letter's language from a localized pack text |

## Adding a jurisdiction

1. Create `jurisdictions/<id>/pack.yaml` (schema: `schemas/jurisdiction/0.1.json`), using
   `extends` if a more general pack exists.
2. Every legal basis, deadline and authority is a fact: `source_url` to an **official**
   text, a short verbatim `quote`, and `verification: needs_verification` unless you
   checked the quote against the source yourself (then add `checked_on`).
3. Add one template per language and run `uv run pytest`: every template is rendered with
   full and minimal student data, and the output must carry the disclaimer.
