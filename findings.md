# Rolling Chess Findings

## Project Context

- Repository started as an empty git project.
- The approved design spec was committed as `bd4b02d Add rolling chess design spec`.
- The project will use a Python-first engine, then a local Python web backend and browser UI.

## Key Design Decisions

- Board topology is a horizontal cylinder: files wrap, ranks do not.
- Sliding pieces may use any unobstructed valid route to a target.
- Castling is standard-only and does not use wrapped routes.
- En passant can cross the `a`/`h` boundary.
- First rules engine excludes threefold repetition and the fifty-move adjudication rule.

## Implementation Notes

- Prefer focused constructed-position tests for topology edge cases.
- Public engine APIs should use clear coordinate notation where practical.
- The CLI and web backend must call public APIs, not private movement helpers.

