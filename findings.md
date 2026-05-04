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

## LAN Online Play Context

- The approved LAN spec is `docs/superpowers/specs/2026-05-04-lan-online-play-start-page-design.md`.
- Current environment initially lacks `fastapi`, `uvicorn`, and `websockets`; `httpx` is available.
- The repo has uncommitted UI changes in `frontend/index.html`, `frontend/src/main.js`, `frontend/src/styles.css`, and `tests/test_web_api.py`. Implementation must work with those changes and not revert them.
- Existing `web.py` uses `http.server` and in-memory `GameStore`; this will be replaced by FastAPI while keeping local game semantics.

## AI Implementation Context

- The approved AI spec is `docs/superpowers/specs/2026-05-04-ai-selfplay-value-model-design.md`.
- Current environment has `numpy` but does not have `torch`; model and training modules should import PyTorch lazily so search AI and gameplay still work.
- First playable AI should be search-based and rule-engine-authoritative; trained value model is only a leaf evaluator for experimental mode.
- AI browser/API validation used `easy` difficulty for interaction speed; `normal` depth-2 search is covered by unit tests.
- The local port 8000 was occupied by an older server process during browser testing; stopping that process and starting the latest server fixed the stale API surface.

## UI Flow Fix Context

- The previous frontend clock logic decremented on every render once a state was ongoing, which made clocks start immediately after entering any game route.
- AI move UX required splitting the frontend flow into `player-moves` followed by `ai-move`; returning both states from a single endpoint would still hide the player's move until after AI search completed.
- Browser validation confirmed local, AI, and online waiting states now keep clocks at `10:00` until white's first move has landed.

## UI Move Visibility Context

- `MoveRecord` previously carried capture metadata but not the moving piece, so the frontend could not reliably display the moved piece in history after reload/import or online sync.
- Adding optional `piece` and `piece_symbol` fields keeps old saved histories loadable while making new move history entries richer.
- Last-move square highlighting works naturally in 15x8 view because each visible square is rendered from the same real board square id.
