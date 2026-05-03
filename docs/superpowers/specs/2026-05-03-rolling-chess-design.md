# Rolling Chess Design

## Summary

Rolling Chess is a chess variant played on a standard 8x8 board where the `a` and `h` files are connected. The ranks do not wrap. All pieces use this horizontal cylinder topology for movement and attacks, including pawn captures and en passant.

The project will be built in three phases:

1. Build a Python rules engine.
2. Add a local Python backend and browser-based single-device UI.
3. Expand into a fuller game experience.

The first phase is the foundation. It must provide complete game legality for normal play, but it will not include threefold repetition, the fifty-move rule, clocks, online play, or formal PGN support.

## Goals

- Model a horizontally wrapped chessboard with files `a` through `h` and ranks `1` through `8`.
- Support complete legal move generation for regular game play.
- Keep the rules engine independent from any UI.
- Provide a thin CLI for manual smoke testing before a browser UI exists.
- Leave a clear path for a local browser UI that reuses the Python rules engine.

## Non-Goals

- No threefold repetition rule in the first engine version.
- No fifty-move rule in the first engine version.
- No chess clocks.
- No network multiplayer.
- No AI opponent in the first version.
- No full algebraic notation or PGN export in the first version.

## Rules

The board keeps ordinary chess coordinates from `a1` to `h8`. Internally, files are represented as `0..7` and ranks as `0..7`.

Files wrap horizontally:

- Moving left from file `a` reaches file `h`.
- Moving right from file `h` reaches file `a`.
- Ranks never wrap. A move that goes below rank `1` or above rank `8` is off board.

Pieces, attacks, and special moves use this topology unless explicitly stated otherwise.

### Piece Movement

Kings can move one step in any direction. Horizontal and diagonal king moves can cross the `a`/`h` boundary.

Queens combine rook and bishop movement under the wrapped topology.

Rooks move vertically without wrapping and horizontally with file wrapping.

Bishops move diagonally. Each diagonal step changes the rank by one and changes the file by one with wrapping. The diagonal ray stops when its next rank would be off board.

Knights use their standard offsets. File offsets wrap, while rank offsets must remain on board.

Pawns move forward by color as usual. Their forward movement does not wrap because rank movement does not wrap. Their diagonal capture files wrap, so a white pawn on `a5` can capture on `h6` and a black pawn on `h4` can capture on `a3`.

### Sliding Paths

For sliding pieces, a source and target can sometimes be connected by more than one route. A move is legal if at least one geometrically valid route from source to target is unobstructed.

Examples:

- A rook on `a4` can reach `e4` through `b4-c4-d4` or through `h4-g4-f4`.
- If either route is clear, the rook move from `a4` to `e4` is available.
- A bishop on `a1` can move to `h2` because the file wraps while the rank increases.

Path enumeration must be implemented as a reusable board helper, not duplicated inside each piece rule.

### Castling

Castling follows standard chess exactly.

- White kingside castling is `e1-g1` with the rook from `h1`.
- White queenside castling is `e1-c1` with the rook from `a1`.
- Black kingside castling is `e8-g8` with the rook from `h8`.
- Black queenside castling is `e8-c8` with the rook from `a8`.

The wrapped board does not create additional castling routes. Castling still requires the standard empty squares, unchanged castling rights, no current check, and no king transit through attacked squares.

### En Passant

En passant follows standard chess timing and rank rules, but pawn adjacency uses wrapped files.

Example: if a black pawn moves from `h7` to `h5`, a white pawn on `a5` may capture en passant on the immediately following move by moving to `h6`.

### Promotion

Promotion follows standard chess. A pawn that reaches the last rank must promote to queen, rook, bishop, or knight.

### Legal Game State

The engine must support:

- Legal move generation.
- Applying legal moves.
- Rejecting illegal moves.
- Check detection.
- Checkmate detection.
- Stalemate detection.
- Castling.
- En passant.
- Promotion.

The first version will not adjudicate threefold repetition or the fifty-move rule.

## Architecture

The phase B engine will be a Python package under `src/rolling_chess`. It will not depend on the browser UI.

Recommended modules:

- `board.py`: square parsing, coordinate conversion, file wrapping, board storage, and sliding path helpers.
- `pieces.py`: piece colors, piece types, piece values, and simple piece data structures.
- `moves.py`: move data structures, promotion, castling flags, en passant flags, and move parsing helpers.
- `state.py`: `GameState`, side to move, castling rights, en passant target, halfmove clock, fullmove number, and move application.
- `rules.py`: pseudo-legal move generation, legal move filtering, attack detection, check, checkmate, and stalemate.
- `notation.py`: simple coordinate notation such as `e2e4` and `a7a8q`.
- `cli.py`: a thin manual-play entry point.
- `web.py`: added in phase A for the local HTTP API.

The package should expose a compact public API:

```python
from rolling_chess import Color, GameState, Move

state = GameState.initial()
moves = state.legal_moves()
state = state.apply_move(Move.from_uci("e2e4"))
in_check = state.is_check(Color.BLACK)
result = state.result()
```

`apply_move()` should accept only legal moves in normal public use. Illegal moves should raise a clear exception.

## Data Model

`Color` should represent white and black.

`PieceType` should represent king, queen, rook, bishop, knight, and pawn.

`Piece` should contain a color and piece type.

`Square` can be represented internally as a compact coordinate pair or integer index, but public APIs should accept and return standard coordinate strings where practical.

`Move` should include:

- Source square.
- Target square.
- Optional promotion piece.
- Move kind when needed: normal, castle, en passant, or promotion.

`GameState` should include:

- Board position.
- Side to move.
- Castling rights.
- En passant target square.
- Halfmove clock, even though the fifty-move rule is not adjudicated in the first version.
- Fullmove number.
- Optional move history for CLI display and later undo support.

## Move Generation

Move generation is split into two layers.

The pseudo-legal layer generates moves that obey piece movement, board topology, occupancy, captures, promotion shape, en passant shape, and castling shape.

The legal layer filters pseudo-legal moves by applying each move to a copied state and rejecting moves that leave the moving side's king in check.

Attack detection must use the same wrapped movement rules as move generation. The implementation should avoid separate, inconsistent movement definitions for "moves" and "attacks".

## Error Handling

The engine should define explicit exceptions:

- `InvalidSquareError`: a square string is outside `a1..h8`.
- `InvalidMoveFormatError`: a move string cannot be parsed.
- `IllegalMoveError`: the move is well-formed but illegal in the current state.
- `GameOverError`: a move is attempted after checkmate or stalemate.

Phase A web endpoints should translate these into structured JSON errors with concise messages for the UI.

## CLI

The CLI is a smoke-test tool, not a full product UI.

It should support:

- Starting from the initial position.
- Printing the board.
- Showing the side to move.
- Accepting coordinate moves such as `e2e4` and `a7a8q`.
- Reporting illegal moves.
- Reporting check, checkmate, or stalemate.

The CLI should call the public engine API rather than using private rule helpers directly.

## Phase A Browser UI

The browser UI will use the Python engine through a local HTTP backend. The rules will not be rewritten in JavaScript.

Recommended backend endpoints:

- `POST /api/games`: create a new game.
- `GET /api/games/{game_id}`: return board state, side to move, legal moves, check status, and result.
- `POST /api/games/{game_id}/moves`: submit a move and return the updated state.
- `POST /api/games/{game_id}/undo`: optional in phase A; can be deferred to phase C.

The first UI should support local two-player play on one device.

Required UI behavior:

- Render an 8x8 chessboard.
- Select a piece and highlight legal target squares.
- Submit moves to the backend for validation.
- Prompt for promotion choice.
- Show side to move.
- Show check, checkmate, stalemate, and illegal-move messages.

The UI may visually hint at wrapped moves through edge highlights or target markers, but the board remains a normal square grid.

## Phase C Extensions

Later product features should build on the stable engine API:

- Undo and redo with move history.
- Save and load local games.
- Custom PGN-like notation for the variant.
- Threefold repetition and fifty-move rule adjudication.
- Position editor.
- Simple AI or external engine interface.
- Online multiplayer.

These are excluded from the first implementation plan unless explicitly promoted later.

## Testing

The engine should use `pytest`.

Core test areas:

- Square parsing and file wrapping.
- King moves across `a`/`h`.
- Knight moves across `a`/`h`.
- Rook horizontal movement with two possible routes.
- Rook movement blocked on one route but legal through the other.
- Bishop diagonal wrapping such as `a1-h2`.
- Queen movement as rook plus bishop.
- White and black pawn diagonal captures across `a`/`h`.
- Cross-boundary en passant.
- Standard-only castling behavior.
- Rejection of moves that leave the moving king in check.
- Check detection under wrapped attacks.
- Checkmate and stalemate detection.
- Promotion.
- CLI smoke test for a short legal move sequence.

Tests should prefer focused constructed positions over long full-game sequences. The initial position can be used for regression checks, but expected legal move counts must be derived from the variant rules rather than copied from standard chess.

## Acceptance Criteria

Phase B is complete when:

- A Python package exposes `GameState`, `Move`, and related public types.
- The engine can create an initial position, list legal moves, apply legal moves, reject illegal moves, and report game result.
- Castling, en passant, promotion, check, checkmate, and stalemate are implemented.
- Cross-boundary movement and capture behavior is covered by tests.
- The CLI can run a manual local game from the terminal.
- The test suite passes.

Phase A is complete when:

- A local Python backend serves game state and validates moves.
- A browser UI can play a full local two-player game.
- The UI handles promotion, illegal moves, check, checkmate, and stalemate.
- No browser-side rule implementation duplicates the Python engine.

Phase C is complete when the selected product extensions are implemented without changing the core semantics of the phase B public API.

## Open Decisions Deferred To Implementation

These choices do not change the project definition and can be settled during implementation:

- Whether `Square` is stored as a tuple, dataclass, or compact integer internally.
- Whether the initial backend uses in-memory game storage only.
- Whether phase A uses plain TypeScript, a small frontend framework, or server-rendered HTML.
- Exact visual style for wrapped move hints.

