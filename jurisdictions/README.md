# Jurisdiction packs

Legal bases, deadlines, supervisory authorities and document templates per country or
region. Each folder holds a `pack.yaml` (schema:
[`schemas/jurisdiction/0.1.json`](../schemas/jurisdiction/0.1.json)) and its templates.
Templates are filled with profile and student data **on the student's device**; nothing is
sent anywhere.

| Pack | Extends | Access request based on | Letter languages |
|---|---|---|---|
| `eu` | | GDPR Arts. 12, 15, 22 | en, es |
| `es` | `eu` | + LOPDGDD art. 13 | es (en from `eu`) |
| `uk` | | UK GDPR Art. 15 and 12A (Data (Use and Access) Act 2025) | en |
| `us` | | FERPA, 34 CFR 99.10-99.11 | en |
| `co` | | Ley 1581 de 2012 arts. 8, 14; Decreto 1377 de 2013 art. 21; Ley 1755 de 2015 | es |

See [docs/templates.md](../docs/templates.md) to add a pack or a language.

**Nothing here is legal advice.** Every fact carries its source; facts marked
`needs_verification` have not been checked against that source by a person.
