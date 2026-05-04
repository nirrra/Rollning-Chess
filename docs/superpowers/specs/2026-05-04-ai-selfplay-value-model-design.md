# AI Opponent, Self-Play, and Value Model Design

## Purpose

Rolling Chess needs a playable human-vs-computer mode and a path toward learned evaluation. The first version should not attempt a full AlphaZero-style system. It should ship a reliable search AI first, then add a lightweight self-play and PyTorch value-model pipeline that can improve the search leaf evaluation over time.

The goal is a working loop:

1. Human can play against AI in the browser.
2. The engine can generate self-play data without external chess records.
3. A small PyTorch value model can train from self-play JSONL.
4. Experimental AI can use the trained model as a search leaf evaluator.

The initial model is expected to be weak. The first milestone is correctness, reproducibility, and extensibility.

## Confirmed Product Decisions

- Overall route: search AI first, self-play and training pipeline in parallel.
- Model type: value model only.
- Training framework: PyTorch.
- First training target: lightweight local experiment, not strong chess performance.
- Human-vs-AI mode: player chooses white or black.
- AI difficulty levels:
  - `easy`
  - `normal`
  - `experimental`
- Project layout:
  - AI code: `src/rolling_chess/ai/`
  - Self-play data: `data/selfplay/*.jsonl`
  - Model output: `models/value.pt`
  - CLI command group: `rolling-chess-ai`
- Self-play labels: final game result from the current-to-move side's perspective.
- Self-play max length: 160 half-moves; games that exceed this are labeled draw.
- Model use in play: value model evaluates search leaf positions only; legal moves and search remain rule-engine driven.

## Non-Goals For The First Version

- No full MCTS.
- No policy model.
- No distributed or long-running training scheduler.
- No model promotion league.
- No cloud training.
- No GPU requirement.
- No forced use of a model file for normal gameplay.
- No direct model-generated moves that bypass legal move validation.

## AI Module Architecture

New package:

```text
src/rolling_chess/ai/
  __init__.py
  cli.py
  encoding.py
  evaluate.py
  search.py
  selfplay.py
  train.py
  value_model.py
```

### `evaluate.py`

Provides deterministic handwritten evaluation.

Responsibilities:

- Evaluate a `GameState` from the side-to-move perspective.
- Handle terminal positions:
  - current side checkmated: large negative score
  - opponent checkmated after move: large positive score through resulting state
  - stalemate: zero
- Score non-terminal positions with simple terms:
  - material
  - legal move count / mobility
  - check status
  - basic king safety
  - optional pawn advancement

The score should be symmetric: flipping perspective should invert the sign as far as practical.

### `search.py`

Provides move selection.

Public concepts:

- `Difficulty.EASY`
- `Difficulty.NORMAL`
- `Difficulty.EXPERIMENTAL`
- `choose_move(state, difficulty, model_path=None, rng=None)`

Behavior:

- `easy`: chooses a legal move with light randomness. It may prefer captures/checks but must remain fast.
- `normal`: alpha-beta / negamax search with handwritten evaluation.
- `experimental`: alpha-beta / negamax search with model leaf evaluation if `models/value.pt` exists and loads; otherwise automatic fallback to `normal`.

Search requirements:

- Never returns illegal moves.
- Handles no-legal-move positions by returning `None`.
- Uses deterministic ordering when seeded.
- Includes depth limits by difficulty.
- Avoids excessive runtime in the browser flow.

Suggested first depths:

- `easy`: random legal move or depth 1.
- `normal`: depth 2.
- `experimental`: depth 2 with model leaf evaluation.

### `encoding.py`

Converts a `GameState` into a tensor suitable for PyTorch.

First version tensor:

```text
shape = (18, 8, 8)
dtype = float32
```

Channels:

- 12 piece planes: white/black x K,Q,R,B,N,P
- 1 side-to-move plane: all ones for white to move, all zeros for black to move
- 4 castling-right planes: K,Q,k,q
- 1 en-passant target plane

Files remain 8 columns. The A/H wrap is encoded implicitly through legal move generation, not by expanding the tensor.

### `value_model.py`

Defines a small value network:

- Input: `(18, 8, 8)`
- Output: one scalar in `[-1, 1]`
- Final activation: `tanh`

Suggested first architecture:

- 2-3 small convolution blocks
- flatten or global pooling
- small linear head

The model predicts value from the side-to-move perspective. It does not output a move.

### `selfplay.py`

Generates training data by playing AI against itself.

Default behavior:

- `normal` vs `normal`
- max 160 half-moves
- draw if max length is exceeded
- optional opening randomness to avoid identical games
- JSONL output to `data/selfplay/YYYYMMDD-HHMMSS.jsonl`

Each sampled position is stored before the move is made, with its final label filled after the game finishes.

### `train.py`

Reads JSONL data and trains the value model.

Default behavior:

- Read all `*.jsonl` under `data/selfplay`.
- Convert stored states with `GameState.from_dict`.
- Train small CNN with MSE loss.
- Save model to `models/value.pt`.
- Print training loss and number of samples.

Training should be able to run on CPU for a small local experiment.

### `cli.py`

Provides:

```bash
rolling-chess-ai selfplay
rolling-chess-ai train
rolling-chess-ai evaluate
```

Suggested arguments:

```bash
rolling-chess-ai selfplay --games 100 --max-plies 160 --out data/selfplay
rolling-chess-ai train --data data/selfplay --out models/value.pt --epochs 5
rolling-chess-ai evaluate --model models/value.pt --games 20
```

## Training Data Format

Each JSONL line is one sample:

```json
{
  "state": {},
  "turn": "white",
  "result": 1.0,
  "ply": 23,
  "game_id": "20260504-001"
}
```

`state` is `GameState.to_dict(include_legal_moves=false)`.

`result` is from the current-to-move side's perspective:

- `+1.0`: current-to-move side eventually wins
- `-1.0`: current-to-move side eventually loses
- `0.0`: draw

For example, if white eventually wins:

- samples where `turn == "white"` get `+1.0`
- samples where `turn == "black"` get `-1.0`

## Human-vs-AI Backend API

AI sessions are separate from local games and LAN rooms.

`AIGameSession`:

- `game_id`
- `state: GameState`
- `player_color`
- `ai_color`
- `difficulty: easy | normal | experimental`
- `model_path`
- `last_ai_move`
- `created_at`
- `updated_at`

The AI game store is in memory for the first version.

### `POST /api/ai/games`

Request:

```json
{
  "player_color": "white",
  "difficulty": "normal"
}
```

Response:

```json
{
  "game_id": "...",
  "state": {},
  "player_color": "white",
  "ai_color": "black",
  "difficulty": "normal",
  "last_ai_move": null
}
```

If the player chooses black, the backend creates the initial state and immediately makes the AI's first white move before returning the response.

### `GET /api/ai/games/{game_id}`

Returns the current AI game session snapshot.

### `POST /api/ai/games/{game_id}/moves`

Request:

```json
{ "move": "e2e4" }
```

Flow:

1. Validate that the session exists.
2. Validate that the game is not over.
3. Validate that it is the player's turn.
4. Apply the player's legal move.
5. If the game is still ongoing, choose and apply an AI move.
6. Return updated session state and `last_ai_move`.

Errors:

- unknown game
- invalid difficulty
- invalid player color
- game over
- not player turn
- illegal move
- AI has no move

## Frontend UI Design

### Start Page

Add a `Play vs AI` section:

- Player color selector: `White` / `Black`
- Difficulty selector: `Easy` / `Normal` / `Experimental`
- Start button

The section should fit the existing parchment/atlas visual style and sit beside or below the local/LAN options without turning the page into a marketing screen.

### AI Game Route

Route:

```text
/game/ai/{game_id}
```

Behavior:

- Reuse the current board.
- Player strip shows `You`.
- Opponent strip shows `AI · Easy/Normal/Experimental`.
- If player chose black, initial board already includes AI's first move.
- Player can only move on their own turn.
- During AI response, status says `AI thinking`.
- History shows both player and AI moves.

Online room logic and AI game logic must stay separate.

### AI Mode Controls

Right-side actions in AI mode:

- `New AI`
- `Back`
- `New Local`

The first version does not support AI `Undo`, `Redo`, `Save`, or `Load`.

## Model Fallback Behavior

`experimental` must be safe by default:

- If `models/value.pt` does not exist, use normal handwritten evaluation.
- If model loading fails, use normal handwritten evaluation and expose a warning in logs or session metadata.
- If model inference fails during move selection, fall back for that move rather than crashing the game.

This prevents the user-facing game from depending on successful training.

## Testing Plan

### Stage 1: Search AI

Tests:

- AI returns a legal move from the initial position.
- AI returns `None` from terminal positions with no legal moves.
- Normal difficulty returns legal moves across several constructed positions.
- Easy difficulty is reproducible with a fixed seed.
- Search does not mutate the input `GameState`.

### Stage 2: AI Game API

Tests:

- Creating an AI game as white does not trigger an immediate AI move.
- Creating an AI game as black triggers an immediate AI white move.
- Player move is followed by an AI move when game remains ongoing.
- Move out of turn is rejected.
- Illegal move is rejected.
- Invalid difficulty is rejected.

### Stage 3: Start Page and AI UI

Tests:

- Start Page renders `Play vs AI`.
- Starting AI game routes to `/game/ai/{game_id}`.
- White player can make a first move and receive an AI reply.
- Black player sees an AI opening move.
- Non-player-turn pieces cannot be selected.
- 8x8 and 15x8 views still work.

### Stage 4: Self-Play and Training

Tests:

- `selfplay` writes JSONL.
- Each JSON line contains `state`, `turn`, `result`, `ply`, and `game_id`.
- Stored states can be loaded with `GameState.from_dict`.
- Results are only `-1.0`, `0.0`, or `1.0`.
- Max-plies games are marked draw.
- `train` can train on a tiny generated dataset and save `models/value.pt`.

### Stage 5: Experimental Model Integration

Tests:

- Experimental chooses a legal move when a model exists.
- Experimental falls back to normal when model is missing.
- Experimental falls back safely when model loading fails.
- AI API can create and play an experimental AI game.
- Full test suite passes.

## Acceptance Criteria

- Start Page can launch a human-vs-AI game.
- Player can choose white or black.
- Player can choose `Easy`, `Normal`, or `Experimental`.
- AI always moves through the rules engine and never bypasses legal move validation.
- AI responds automatically after the player's legal move.
- Search AI is playable without any trained model.
- Self-play can generate local JSONL data.
- PyTorch training can save `models/value.pt`.
- Experimental mode can load the value model as a leaf evaluator.
- Experimental mode falls back safely when no model is available.
- Existing local play and LAN online play continue to pass regression tests.
