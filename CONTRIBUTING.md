# Contributing To Rolling Chess

Thanks for helping improve Rolling Chess. This project is maintained as a lightweight, maintainer-led open source project. Keep contributions focused, testable, and aligned with the horizontal-cylinder chess rules.

## Project Rules Source

The authoritative rules design is:

- `docs/superpowers/specs/2026-05-03-rolling-chess-design.md`

If a proposed change affects the game rules, start with an issue before opening a pull request. Rule changes must update the relevant documentation and include tests.

## Development Setup

Use Python 3.11 or newer.

```powershell
python -m pip install -e .
python -m pytest
```

Run the local browser UI:

```powershell
$env:PYTHONPATH='src'
python -m rolling_chess.web --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`.

## Test Before Opening A PR

Run the relevant checks locally:

```powershell
python -m pytest
python -m compileall -q src tests
node --check frontend/src/main.js
```

If you change only documentation, say so in the pull request. CI still runs the baseline checks.

## Issue Types

Use the matching GitHub issue template:

- Bug report: broken behavior, crashes, invalid legal moves, or UI/API errors.
- Rules question: ambiguous Rolling Chess rule or edge case.
- Feature request: new capability such as AI, position editor, save improvements, or notation.
- Test case: a specific position or move sequence that should be added to the suite.
- Docs: README, contribution, API, or rule documentation improvements.

For rule issues, include:

- Board position.
- Side to move.
- Candidate move.
- Expected behavior.
- Actual behavior.

## Pull Request Expectations

- Keep each PR focused on one issue or one clear change.
- Add or update tests for engine, Web API, or behavior changes.
- Do not mix unrelated formatting or refactors with functional changes.
- Do not duplicate rules in the frontend. The Python engine is authoritative.
- Explain any public API change and how users should adapt.

## Review Criteria

Maintainer review checks whether the PR:

- Matches the approved Rolling Chess rules.
- Covers `a`/`h` wrapping edge cases when relevant.
- Keeps rank movement non-wrapping.
- Preserves standard-only castling.
- Avoids frontend-side rule duplication.
- Includes focused tests.
- Passes CI.

## Community Conduct

Be direct, technical, and respectful. See `CODE_OF_CONDUCT.md`.

