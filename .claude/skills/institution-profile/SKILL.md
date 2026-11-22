---
name: institution-profile
description: Adds or updates a Descargo institution profile (profiles/<country>/<institution>.yaml) with sourced, verifiable policy facts such as AI-use rules, similarity thresholds, regulations, deadlines and contacts. Use when the user names a university, faculty or degree to support, or asks to check or fix a profile's facts.
license: AGPL-3.0-or-later
metadata:
  project: descargo
---

# Institution profile

Schema: `schemas/profile/0.1.json`. Overview and current profiles: `profiles/README.md`.

## Steps

1. Pick the path `profiles/<country>/<id>.yaml` (ISO country code, short lowercase id).
   The tree is institution → faculties → degrees → courses; a lower level refines its parent
   (AI policy, thresholds, self-plagiarism rule and tools override; regulations, deadlines
   and contacts accumulate). Copy the shape of an existing profile such as `profiles/es/uah.yaml`.
2. Find each policy in an **official** source only: the institution's own site, its gazette
   or regulations, an official PDF. Never a blog, forum, news article or AI answer.
3. Write every value as a fact:

   ```yaml
   value: {kind: indicative, percent: 24, applies_to: doctoral thesis}
   source_url: https://…            # the official document itself
   effective_date: 2026-10-01       # if the source says
   checked_on: 2026-11-23           # only with verification: verified
   verification: verified           # or needs_verification (default)
   quote: "…"                       # short verbatim excerpt supporting the value
   note: "…"                        # caveats, what was searched
   ```

4. `verified` only if you fetched the source and found the quote in it yourself (for
   example `curl -sL <url> | pdftotext - - | grep -F "<quote>"`). If the site blocks scripts,
   or you could not read it, leave `needs_verification` and say why in `note`. A "no rule
   found" is always `needs_verification`: a search can miss a document.
5. Validate and review:

   ```bash
   uv run descargo profile validate
   uv run descargo profile unverified
   uv run descargo profile show <country>/<id>
   uv run pytest tests/test_profiles.py tests/test_cli_profile.py
   ```

6. Add the profile to the table in `profiles/README.md` and a line in `CHANGELOG.md`.
   Then run the `pre-pr-check` skill.

## Report back

List which facts are `verified` and which still need a human, with their source URLs.
