# Issue Triage

This project uses lightweight maintainer-led triage. The goal is to turn incoming reports into reproducible, testable work.

## Labels

Recommended labels:

- `type: bug`
- `type: feature`
- `type: rules-question`
- `type: test-case`
- `type: docs`
- `area: engine`
- `area: web-api`
- `area: frontend`
- `area: docs`
- `priority: high`
- `priority: normal`
- `status: needs-info`
- `status: accepted`
- `status: blocked`

## First Pass

For each new issue:

1. Confirm it uses the right template.
2. Add one `type:*` label.
3. Add one or more `area:*` labels.
4. Ask for missing reproduction details if needed.
5. Close duplicates with a link to the canonical issue.

## Bugs

A bug is actionable when it includes:

- Environment or version details.
- Steps to reproduce.
- Expected behavior.
- Actual behavior.
- For rule bugs, a board position and side to move.

If a bug affects legal move generation, check whether it is covered by the rules spec. If the spec is clear, request or add a failing test. If the spec is unclear, convert the issue into a rules question before changing implementation.

## Rules Questions

Rules questions are handled before implementation.

Use this order:

1. Check `docs/superpowers/specs/2026-05-03-rolling-chess-design.md`.
2. If covered, answer with the relevant rule and close or relabel as a bug.
3. If not covered, discuss the smallest rule clarification.
4. Update documentation and tests before changing engine behavior.

## Features

Feature requests should explain:

- User value.
- Example workflow.
- Whether it affects engine, Web API, frontend, or docs.
- Testing expectations.

Do not accept large feature requests as a single PR if they can be split.

## Test Cases

Test case issues should include:

- Position.
- Side to move.
- Move or result being tested.
- Expected legal/illegal/checkmate/stalemate result.

Prefer focused constructed positions over long game transcripts.

