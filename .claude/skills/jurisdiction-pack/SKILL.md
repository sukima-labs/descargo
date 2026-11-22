---
name: jurisdiction-pack
description: Adds or updates a Descargo jurisdiction pack (jurisdictions/<id>/pack.yaml plus Jinja letter templates) with legal bases, deadlines and supervisory authorities taken from official legal texts. Use when adding a country or region, a new legal basis or deadline, a law change, or a letter in another language.
license: AGPL-3.0-or-later
metadata:
  project: descargo
---

# Jurisdiction pack

Schema: `schemas/jurisdiction/0.1.json`. Current packs: `jurisdictions/README.md`.
Template rules and variables: `docs/en/templates.md` (Spanish: `docs/templates.md`).

## Steps

1. Create `jurisdictions/<id>/pack.yaml`; use `extends` when a more general pack exists
   (for example `es` extends `eu`). Copy the shape of a similar pack.
2. Every legal basis, deadline and authority is a fact: `source_url` to the **official**
   text (official gazette, legislature, regulator), a short verbatim `quote`, and
   `verification: needs_verification` unless you checked the quote against that source
   yourself (then `verified` plus `checked_on`). Note transitions with dates, as the `cl`
   pack does for Ley 19.628 → Ley 21.719.
3. Add one template per language, `access_request.<lang>.md.j2`. Write the **letter only**:
   Descargo adds the student note and the "not legal advice" footer in code. Use only the
   variables listed in `docs/en/templates.md`; keep the tone factual, not a lawyer's opinion.
4. Test: every template is rendered with full and minimal student data and must carry the
   disclaimer.

   ```bash
   uv run pytest tests/test_jurisdictions.py tests/test_access_request.py
   uv run descargo access-request --help
   ```

5. Update the table in `jurisdictions/README.md`, add or update the country's procedure
   guide in `docs/` and `docs/en/` if there is one, add a `CHANGELOG.md` line, then run the
   `pre-pr-check` skill.

## Report back

List the legal facts that are `verified` and those still `needs_verification`, with sources.
