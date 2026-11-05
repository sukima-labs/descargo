# Institution profiles

One YAML file per institution, at `profiles/<country>/<institution>.yaml`, validated by
[`schemas/profile/0.1.json`](../schemas/profile/0.1.json). Inside a file the tree goes
institution → faculties → degrees → courses; a lower level refines its parent's policies
(AI policy, thresholds, self-plagiarism rule and tools are overridden; regulations, deadlines
and contacts accumulate).

Every policy value is a **fact**:

```yaml
value: {kind: indicative, percent: 24, applies_to: doctoral thesis}
source_url: https://…/PROCEDIMIENTO-TURNITIN.pdf   # official source only
effective_date: 2026-10-01      # when the rule applies, if the source says
checked_on: 2026-10-27          # when someone last compared value and source
verification: verified          # or needs_verification (the default)
quote: "…"                      # short verbatim excerpt that supports the value
note: "…"                       # context, caveats, what was searched
```

`verified` means the quote was found in the official source on `checked_on`; it requires
both fields. Everything else is `needs_verification`, including every "no rule found":
a search can miss a document.

```bash
uv run descargo profile validate            # schema + file location checks
uv run descargo profile unverified          # what still needs a human
uv run descargo profile show es/uah --path escuela-doctorado
```

| Profile | Institution | Notes |
|---|---|---|
| `co/luisamigo` | Universidad Católica Luis Amigó | AI guidelines for research, a journal's AI-detector rule, habeas data contact; student regulations still missing |
| `es/uah` | Universidad de Alcalá | Doctoral School modelled as a faculty-level node |
| `us/utexas` | The University of Texas at Austin | Campus-wide Institutional Rules, Chapters 9 and 11 |

Not legal advice. Regulations change; always follow `source_url`.
