# Rolling Chess Progress

## 2026-05-03

- Created implementation tracking files.
- Starting Phase 0 from the approved design spec.
- Verified local Python runtime: Python 3.12.7.
- Verified pytest is available: pytest 7.4.4.
- Current repository files are the design spec plus planning files.
- Phase B first test run failed during collection because tests used relative imports before `tests` was a package.
- Added the Python package scaffold, core engine modules, CLI, and Phase B tests.
- Phase B test gate passed: `python -m pytest` reported 19 passed.
- Phase B API smoke passed after applying `e2e4`; CLI smoke reached the prompt and accepted `quit`.
- Added the local HTTP backend and browser UI.
- Phase A test gate passed: `python -m pytest` reported 21 passed, including web API lifecycle and frontend static resource checks.
- Starting a conservative Phase C baseline: redo and local save/load import-export.
- Initial combined Phase C patch failed because `web.py` context order differed; switching to smaller patches.
- Added redo plus state export/import and frontend Save/Load controls.
- Phase C regression gate passed: `python -m pytest` reported 22 passed.
- Final compile check passed: `python -m compileall -q src tests`.
- Final CLI smoke passed and reached the manual move prompt.
- Frontend JavaScript syntax check passed: `node --check frontend/src/main.js`.
- Local web server started successfully at `http://127.0.0.1:8000/` with health check status 200. Server PID: 36256.
- Repository status reviewed; implementation files are currently untracked because no implementation commit was requested.
- Final health recheck found the first background server had exited; restarting with absolute source path.
- Restarted the local server as PID 36648 and verified `http://127.0.0.1:8000/api/health` returns 200.
- Final regression rerun passed: `python -m pytest` reported 22 passed.

## 2026-05-04

- Starting LAN online play implementation from the approved start page and online play design.
- Confirmed existing working tree has uncommitted frontend UI changes; these must be preserved.
- Checked runtime dependencies: `fastapi`, `uvicorn`, and `websockets` are not currently installed; `httpx` is installed.
- Added LAN online implementation phases to `task_plan.md` and discovery notes to `findings.md`.
- Installed editable project dependencies after approval: FastAPI, Uvicorn, and WebSocket support packages are now available.
- Added `src/rolling_chess/online.py` for in-memory LAN rooms, players, random color assignment, token rejoin, snapshots, and move authorization.
- Replaced the `http.server` web layer with FastAPI/Uvicorn while preserving local game REST endpoints.
- Added online room HTTP endpoints and `/ws/rooms/{room_id}` WebSocket flow.
- Migrated web tests to FastAPI `TestClient` and added room join/rejoin/full-room and WebSocket move synchronization tests.
- LAN backend gate passed: `python -m pytest tests/test_web_api.py` reported 6 passed.
- Added a functional Start Page with nickname persistence, Local Game, Create LAN Room, room-code join, and host instructions.
- Added frontend route handling for `/`, `/game/local`, and `/room/{room_id}`.
- Added online frontend WebSocket connection, token-based room identity storage, reconnect, online move submission, and online-specific controls.
- Restarted the local server on port 8000 with the new FastAPI/Uvicorn backend.
- Browser smoke passed in system Edge: Start Page creates a room, a second browser context joins by code, white moves `E2E4`, and both histories synchronize without console errors.
- Browser smoke passed for local mode: Start Page enters `/game/local`, local `E2E4` works, and board view toggle works.
- Final checks passed: `node --check frontend/src/main.js`; `python -m compileall -q src tests`; `python -m pytest` reported 26 passed.

## 2026-05-04 AI Opponent

- Starting AI opponent and self-play implementation from the approved AI/self-play/value-model design.
- Checked dependencies: `torch` is not installed, `numpy` is installed.
- Added AI phases and validation gates to `task_plan.md`.
- Added AI context notes to `findings.md`.
- Added search AI, handwritten evaluation, and in-memory AI game sessions.
- Added AI REST endpoints for creating games, fetching sessions, and applying player moves followed by automatic AI replies.
- Added Start Page AI controls and `/game/ai/{game_id}` frontend mode using the existing board UI.
- Added self-play JSONL generation, state encoding, lazy PyTorch value model loading, training, evaluation, and `rolling-chess-ai` CLI entrypoint.
- Added AI search/API/self-play/training behavior tests.
- First AI test run failed because pytest's default Windows temp directory was inaccessible in the sandbox; changed tests to use workspace-local `.pytest_tmp/`.
- Validation passed: `node --check frontend/src/main.js`; `python -m compileall -q src tests`; `python -m pytest` reported 37 passed.
- CLI smoke passed: `python -m rolling_chess.ai.cli selfplay --games 1 --max-plies 2 --difficulty easy --out .pytest_tmp\cli-selfplay --seed 11` wrote 2 samples.
- Browser validation initially hit an old server on port 8000 returning 405 for `/api/ai/games`; stopped PID 4316 and restarted the latest server outside the sandbox as PID 29032.
- Browser AI smoke passed: white player started an easy AI game, played `E2E4`, received AI reply `A7A5`, and saw no console errors.
- Browser black-side smoke passed: black player started an easy AI game and saw the AI opening move before their turn.

## 2026-05-04 UI Flow Fixes

- Implemented deferred clock startup with `clockStarted`; local, online, and AI modes now wait until white's first legal move has landed before decrementing clocks.
- Added a fixed top-left Home button on the game screen that returns to the Start Page and cleans up online socket state.
- Split AI frontend move flow into `player-moves` then `ai-move`, so the player's move renders immediately before AI calculation/reply.
- Kept the existing combined `/api/ai/games/{game_id}/moves` endpoint and added `player_state` to its response for compatibility.
- Added API tests for separate AI player/AI move steps and frontend static assertions for Home, clock gating, and new AI endpoints.
- Validation passed: `node --check frontend/src/main.js`; `python -m compileall -q src tests`; `python -m pytest` reported 38 passed.
- Restarted the local web server on port 8000 with the updated code. Server PID: 4672.
- Browser validation passed: local clocks remain `10:00/10:00` before first move; after `E2E4`, black clock starts.
- Browser validation passed: AI normal mode shows `E2E4` and `AI THINKING` before AI reply appears.
- Browser validation passed: AI black mode starts with an AI white move and then black's clock begins.
- Browser validation passed: online waiting room clocks remain `10:00/10:00` before any move.

## 2026-05-04 UI Move Visibility

- Moved the Home button out of fixed positioning and into its own top row in the game layout, so it no longer covers the top player card.
- Extended `MoveRecord` with optional `piece` and `piece_symbol` fields and populated them from the moving piece during move application.
- Updated frontend history formatting so entries show the moved piece, for example `♙ E2E4`.
- Added board highlighting for the latest move's origin and destination squares; repeated squares in 15x8 view highlight together.
- Validation passed: `node --check frontend/src/main.js`; `python -m compileall -q src tests`; `python -m pytest` reported 38 passed.
- Restarted local server on port 8000. Server PID: 17548.
- Browser validation passed: after `E2E4`, history shows `♙ E2E4`, one origin and one destination highlight appear in 8x8, and two origin/two destination highlights appear in 15x8.
