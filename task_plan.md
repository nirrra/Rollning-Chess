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

## LAN Online Play Implementation

### Goal

Implement the approved LAN online play and functional start page design from `docs/superpowers/specs/2026-05-04-lan-online-play-start-page-design.md`.

### Phase Status

| Phase | Scope | Status |
| --- | --- | --- |
| L1 | FastAPI/Uvicorn service migration while preserving local APIs | Complete |
| L2 | Online room model and HTTP room API | Complete |
| L3 | WebSocket online move synchronization | Complete |
| L4 | Start page and local/online frontend routing | Complete |
| L5 | Browser and regression validation | Complete |

### LAN Validation Gates

| Gate | Required checks |
| --- | --- |
| L1 | `python -m pytest tests/test_web_api.py`; static asset checks |
| L2 | Room create/join/rejoin/full-room API tests |
| L3 | WebSocket two-client move and rejection tests |
| L4 | Frontend syntax check; lobby/static smoke tests |
| L5 | Full `python -m pytest`; compile check; browser smoke if available |

## AI Opponent And Self-Play Implementation

### Goal

Implement the approved human-vs-AI, self-play, and value model design from `docs/superpowers/specs/2026-05-04-ai-selfplay-value-model-design.md`.

### Phase Status

| Phase | Scope | Status |
| --- | --- | --- |
| AI1 | Search AI and handwritten evaluation | Complete |
| AI2 | AI game backend API | Complete |
| AI3 | Start Page AI controls and AI route UI | Complete |
| AI4 | Self-play, value model, training CLI | Complete |
| AI5 | Regression, CLI smoke, browser validation | Complete |

### AI Validation Gates

| Gate | Required checks |
| --- | --- |
| AI1 | Search/evaluation unit tests |
| AI2 | AI API tests for white/black player and automatic AI move |
| AI3 | Frontend syntax and browser AI smoke |
| AI4 | Self-play JSONL test; train command behavior with/without PyTorch |
| AI5 | Full `python -m pytest`; compile; frontend check |

## UI Flow Fixes

### Goal

Implement requested gameplay-flow fixes for deferred clocks, a Home button, and immediate player-move rendering before AI calculation.

### Phase Status

| Phase | Scope | Status |
| --- | --- | --- |
| U1 | Clock starts only after white's first legal move lands | Complete |
| U2 | Game-screen Home button returns to Start Page | Complete |
| U3 | AI mode renders player move before AI reply calculation | Complete |
| U4 | Regression and browser validation | Complete |

## UI Move Visibility Fixes

### Goal

Implement requested UI fixes for Home placement and per-move piece visibility.

### Phase Status

| Phase | Scope | Status |
| --- | --- | --- |
| V1 | Move Home into its own top row | Complete |
| V2 | Store and display moved piece in move history | Complete |
| V3 | Highlight last move origin and destination on the board | Complete |
| V4 | Regression and browser validation | Complete |
