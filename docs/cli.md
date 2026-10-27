# Command-line interface

Every command reads files on your device and writes only the output you ask for. None of
them uses the network. `draftwitness COMMAND --help` lists every option.

**Not legal advice.**

| Command | What it does | Details |
|---|---|---|
| `profile list`, `profile show`, `profile validate`, `profile unverified` | List, check and show institution profiles, and the facts a human still has to verify | [Contributing](../CONTRIBUTING.md#adding-or-updating-data) |
| `access-request` | Draft a request for access to the detector report under the law that applies to you | [README](../README.md#usage-so-far); pack authors: [templates](templates.md) |
| `import-report` | Read a downloaded detector report into DraftWitness JSON | [Import](import.md) |
| `audit` | Recompute a similarity percentage after discounting quotations, references, templates and your declared own work | [Audit](audit.md) |
| `inspect` | List what a file contains besides its visible text, before you submit it | [Inspect](inspect.md) |

## Language

- `draftwitness --lang en|es COMMAND …` sets the interface language: messages, and the
  default language of the reports that `audit` and `inspect` write. Without it,
  DraftWitness uses `DRAFTWITNESS_LANG`, then `LC_ALL`, `LC_MESSAGES` and `LANG`, then
  English.
- `audit --language` and `inspect --language` set the report language alone.
  `access-request --language` sets the letter language, which needs a template in that
  language in the jurisdiction pack; by default it is the institution's language.
- Help texts and usage errors (an unknown option, a missing file) are in English for now.

## Output files

- `--out FILE` writes to a file instead of the terminal. PDF output needs `--out`.
  `access-request --out` takes a path without extension and adds `.md` and `.pdf`.
- An existing file is never overwritten unless you pass `--force`.
- An input file is never overwritten, even with `--force`: `--out` must not be the report,
  document, declarations or details file the command reads.
- When `import-report` prints JSON to the terminal, its summary and notes go to standard
  error, so the JSON can be piped or redirected on its own.

## Dates

`--date YYYY-MM-DD` sets the date printed on a letter, audit or inspection report, so that
the same inputs give the same output. It defaults to today.

## Exit status

| Status | Meaning |
|---|---|
| 0 | Done. For `inspect`, this holds whatever the file contains: findings are not failures ([ADR 006](adr/006-pre-submission-inspector.md)). |
| 1 | DraftWitness could not or would not do it: an unreadable file, an unknown profile, an output that would overwrite a file, an invalid profile in `profile validate`. The message says why. |
| 2 | Usage error: an unknown option or option value, or a file that does not exist. |

## Data folders

`--profiles-dir` and `--jurisdictions-dir` point at your own copies of the
[`profiles/`](../profiles/) and [`jurisdictions/`](../jurisdictions/) folders, for example
to try a profile before contributing it. By default the bundled ones are used.
