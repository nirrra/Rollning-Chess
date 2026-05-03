# Rolling Chess Implementation Plan

## Goal

Implement the approved Rolling Chess design in stages, with strict validation before moving to the next stage.

## Source Of Truth

- Design spec: `docs/superpowers/specs/2026-05-03-rolling-chess-design.md`

## Phase Status

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Project scaffold and planning files | Complete |
| B1 | Python package scaffold and core data model | Complete |
| B2 | Board topology, move parsing, and pseudo-legal movement | Complete |
| B3 | Legal move filtering, check, mate, stalemate, special moves | Complete |
| B4 | CLI and strict Phase B tests | Complete |
| A1 | Local HTTP backend using the Python engine | Complete |
| A2 | Browser single-device UI | Complete |
| A3 | Strict Phase A API/UI smoke validation | Complete |
| C | Redo plus local save/load import-export baseline | Complete |
| Final | Full regression and handoff | Complete |

## Implementation Rules

- Do not rewrite browser-side chess rules; the Python engine is authoritative.
- Treat `a` and `h` files as connected for all piece movement and attacks.
- Keep ranks non-wrapping.
- Castling remains standard-only.
- Run tests after each phase boundary.
- Log all failures and fixes in `progress.md`.

## Validation Gates

| Gate | Required checks |
| --- | --- |
| Phase B | `python -m pytest`; CLI smoke test |
| Phase A | `python -m pytest`; API smoke test; browser/static UI asset check |
| Phase C | Tests specific to selected extension plus full regression |
| Final | Full test suite and repository status review |

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| Pytest collection failed for relative imports in tests | Phase B test run 1 | Added `tests/__init__.py` so relative imports resolve |
| Phase C combined patch failed due changed `web.py` context | Phase C edit 1 | Split the change by file and apply against current contents |
| Background web server exited before final health check | Final server check 1 | Restart using an absolute `PYTHONPATH` and verify the process remains reachable |
