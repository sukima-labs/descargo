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
| `ar` | | Ley 25.326 arts. 14, 15; Decreto 1558/2001; Constitución Nacional art. 43 | es |
| `cl` | | Ley 19.628 arts. 12, 16 (until 30-11-2026); Ley 21.719 (from 01-12-2026) | es |
| `co` | | Ley 1581 de 2012 arts. 8, 14; Decreto 1377 de 2013 art. 21; Ley 1755 de 2015 | es |
| `mx` | | LGPDPPSO (public institutions) and LFPDPPP (private ones), both of 2025 | es |
| `pe` | | Ley 29733 art. 19; Reglamento (Decreto Supremo 016-2024-JUS) | es |

See [docs/en/templates.md](../docs/en/templates.md) to add a pack or a language.

**Nothing here is legal advice.** Every fact carries its source; facts marked
`needs_verification` have not been checked against that source by a person.
