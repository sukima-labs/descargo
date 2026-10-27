# ADR 009: The first three detectors

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

The maintainer wants DraftWitness to work with the three detectors that universities use
most. "Work with" means that a student who has the tool's downloaded report can:

1. read it into the common report format (ADR 004), for similarity and, where the tool
   produces one, for AI writing;
2. audit it (ADR 005) or have it explained;
3. name the tool in an access request (already possible for ten tools).

On 2026-10-27, DraftWitness reads only one kind of report: Turnitin's Similarity Report PDF,
in English. There is no adapter for a Turnitin report downloaded in Spanish, for Turnitin's
AI writing report, or for any other tool.

### What is known about use

No reliable, public market-share figure was found. What was found, on 2026-10-27:

- **Turnitin** is the most widely documented tool. Universities in all three of the
  project's countries say they license it on their own pages. In Colombia these include
  Universidad de los Andes, Pontificia Universidad Javeriana, Universidad Distrital and
  Universidad de Cundinamarca; in Spain, Universidad Politécnica de Madrid. Turnitin's AI
  writing indicator is named first on every page found that lists the AI detectors
  colleges use.
- **Compilatio** (Magister, Magister+) is used in Spain and Latin America. Examples are
  UNED in Spain, and Universidad Externado de Colombia and UNAD in Colombia. The maintainer
  received a real Compilatio Magister report from a UNAD course. It shows a 75 % "Textos
  potencialmente generados por la IA" figure next to 1 % similarity, so one report carries
  both kinds of result.
- **Ouriginal** (formerly Urkund) is being withdrawn. Turnitin's migration guide says
  "Ouriginal will be discontinued on June 30, 2026". It is not worth an adapter.
- **SafeAssign** is built into Blackboard Learn and produces an "Originality Report". It is
  common wherever Blackboard is the LMS, mainly in English-speaking countries. It reports
  similarity only.
- **Copyleaks** is reached mostly through LMS integrations, often D2L Brightspace and
  Moodle. It reports both similarity and AI. Several of the pages that list "what AI
  detectors colleges use" name Turnitin, Copyleaks and GPTZero, but those pages are
  secondary and some are written to sell other products.

The project's first users are Spanish speakers in Spain and Colombia. Its main harm case is
an **AI-writing flag**: similarity reports can already be checked against sources, but an AI
score cannot.

## Options

1. **Turnitin, Compilatio, SafeAssign.** Covers the largest installed bases across the
   project's countries. SafeAssign is similarity-only and mostly English.
2. **Turnitin, Compilatio, Copyleaks.** Covers both Spanish-speaking markets and the two
   most-named AI detectors after Turnitin's. Copyleaks reports are multilingual.
3. **Turnitin, SafeAssign, Copyleaks.** Centred on the United States. It leaves out the tool
   the Colombian testers are most likely to meet.

## Decision

Option 2: **Turnitin, Compilatio and Copyleaks**. SafeAssign comes fourth, when there is
demand from students.

For each tool, both kinds of report are in scope, in English and Spanish. The order of work:

1. **Compilatio Magister and Magister+, similarity and AI, in Spanish.** Testers are in
   Colombia, and a real layout is already available to study.
2. **Turnitin: the AI writing report, and the Spanish interface** of both reports.
3. **Copyleaks, similarity and AI.**

### Rules for every adapter

- **Real reports are needed to learn each layout.** Real reports contain personal data. They
  are read on the maintainer's machine only and never committed, and the names in them are
  never quoted. They are deleted when the adapter is done.
- **Tests use synthetic fixtures.** Each fixture is a PDF built by a script in
  `tests/fixtures/`, which reproduces the layout with invented text and invented names.
- **Personal data is dropped**, as in ADR 004. The depositor's name, the group members'
  names and document IDs that identify a person are never stored.
- **No value is guessed.** What cannot be read is left empty, with a warning.

### What an AI result means here

Reading an AI writing result into the report format is in scope. How DraftWitness explains
it is a separate decision for the next ADR (010; the LLM ADR moves to 011). That covers
what the tool claims and its documented error rates, which passages are flagged, and what a
flag does not prove. Until that ADR is decided, the audit shows an AI figure as the tool's
statement, without discounting or recomputing it. ADR 002 still applies: DraftWitness never
predicts or lowers a score.

## Consequences

- An adapter needs real reports. The maintainer, or testers who agree to it, provide
  downloaded reports; the project never asks students to send them.
- The registry stops assuming that every PDF is a Turnitin report. It asks each adapter
  whether it recognises the file, and says which tools it can read when none does.
- More layouts mean more maintenance. Vendors change their reports without notice, so each
  adapter records the layout versions it was written against and refuses unknown ones
  instead of misreading them.
