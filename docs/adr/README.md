# Architecture decision records

Each ADR records one decision: the context, the options considered, the decision, and its
consequences. ADRs are never rewritten after they are accepted; a later ADR supersedes an
earlier one and says so.

| ADR | Title | Status |
|---|---|---|
| [001](001-local-first.md) | Local-first, no backend | Accepted |
| [002](002-non-goals.md) | Non-goals: no evasion | Accepted |
| [003](003-stack.md) | Technology stack and repository layout | Accepted |
| [004](004-report-schema.md) | Common report schema | Accepted |
| [005](005-similarity-auditor.md) | Similarity auditor: inputs, discount rules, precision | Accepted |
| [006](006-pre-submission-inspector.md) | Pre-submission inspector: what it reports and how | Accepted |
| [007](007-web-build.md) | Static in-browser build | Accepted |
| [008](008-institution-facts-from-students.md) | Asking students for institution facts | Accepted |

To propose a decision, copy the structure of an existing ADR, number it with the next free
number, set its status to **Proposed**, and open a pull request before implementing it.
