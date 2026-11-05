# ADR 002: Non-goals — no evasion

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

Detectors produce false positives, and the people harmed are often those with the least
power to contest them: students writing in a second language, neurodivergent students, and
students whose style is simply plain. A defense tool is legitimate and needed.

A tool that also helps text slip past detectors is a different thing. It would help
misconduct, it would expose users and maintainers to legal risk in jurisdictions that
regulate contract-cheating services, and above all it would destroy the credibility of the
evidence Descargo produces: a panel cannot trust a report from a tool that also sells
the disguise.

## Decision

Descargo provides **evidence**. It never modifies the student's work. Out of scope,
permanently:

1. Rewriting, paraphrasing, "humanising", or otherwise transforming text, including
   suggesting rewrites.
2. Predicting, simulating or lowering detector scores, including "check your AI score before
   you submit" loops.
3. Removing, detecting-in-order-to-remove, or spoofing watermarks or provenance signals.
4. Altering a submitted file in any way, including stripping metadata or characters. The
   `pre` inspector **reports** what it finds; the student decides what to do with their own
   file using their own tools.

## Where the line is

| In scope | Out of scope |
|---|---|
| Showing which invisible characters or metadata a file contains | Removing them for the student |
| Explaining a detector report the student already has | Producing a score to optimise against |
| Comparing several detectors' results on the **submitted, sealed** version, after a flag, to show inconsistency | Running detectors on drafts to tune the text before submission |
| Auditing which matches are properly quoted and cited | Suggesting how to reword a match |
| Recording the writing process (phase 2) | Fabricating a writing history |

Multi-detector comparison is therefore a `post` feature only and operates on the sealed
submitted file.

## Consequences

- Pull requests implementing anything in the out-of-scope list are closed, however they are
  framed.
- Some students will want an evasion feature and go elsewhere. That is accepted.
- Every generated document can state truthfully that Descargo does not alter text.
