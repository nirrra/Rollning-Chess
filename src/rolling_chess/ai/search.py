from __future__ import annotations

import math
import random
from enum import Enum
from pathlib import Path
from typing import Callable

from .evaluate import MATE_SCORE, evaluate_state, static_evaluate_state
from ..moves import Move, MoveKind
from ..pieces import PieceType
from ..state import GameState

Evaluator = Callable[[GameState], float]
MAX_CACHED_MODELS = 2
_MODEL_EVALUATOR_CACHE: dict[Path, tuple[int, int, Evaluator]] = {}


class Difficulty(Enum):
    EASY = "easy"
    NORMAL = "normal"
    EXPERIMENTAL = "experimental"

    @classmethod
    def from_value(cls, value: str) -> "Difficulty":
        try:
            return cls(value.lower())
        except ValueError as exc:
            raise ValueError(f"invalid difficulty: {value}") from exc


def choose_move(
    state: GameState,
    difficulty: Difficulty | str = Difficulty.NORMAL,
    model_path: str | Path | None = None,
    rng: random.Random | None = None,
) -> Move | None:
    difficulty = Difficulty.from_value(difficulty) if isinstance(difficulty, str) else difficulty
    legal_moves = list(state.legal_moves())
    if not legal_moves:
        return None

    rng = rng or random.Random()
    if difficulty is Difficulty.EASY:
        return _choose_easy(state, legal_moves, rng)

    evaluator = static_evaluate_state
    if difficulty is Difficulty.EXPERIMENTAL:
        evaluator = _model_evaluator_or_default(model_path)
    depth = 2
    return _choose_search(state, legal_moves, depth, evaluator)


def _choose_easy(state: GameState, legal_moves: list[Move], rng: random.Random) -> Move:
    tactical = [move for move in legal_moves if _move_priority(state, move) >= 100]
    pool = tactical if tactical and rng.random() < 0.65 else legal_moves
    return rng.choice(sorted(pool, key=lambda move: move.to_uci()))


def _choose_search(
    state: GameState, legal_moves: list[Move], depth: int, evaluator: Evaluator
) -> Move:
    best_score = -math.inf
    best_move = legal_moves[0]
    for move in sorted(legal_moves, key=lambda candidate: _move_priority(state, candidate), reverse=True):
        next_state = state.apply_move(move)
        score = -_negamax(next_state, depth - 1, -math.inf, math.inf, evaluator)
        if score > best_score or (score == best_score and move.to_uci() < best_move.to_uci()):
            best_score = score
            best_move = move
    return best_move


def _negamax(
    state: GameState, depth: int, alpha: float, beta: float, evaluator: Evaluator
) -> float:
    legal_moves = list(state.legal_moves())
    if not legal_moves:
        return -MATE_SCORE if state.is_check() else 0.0
    if depth <= 0:
        return evaluator(state)

    value = -math.inf
    for move in sorted(legal_moves, key=lambda candidate: _move_priority(state, candidate), reverse=True):
        score = -_negamax(state.apply_move(move), depth - 1, -beta, -alpha, evaluator)
        value = max(value, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return value


def _move_priority(state: GameState, move: Move) -> int:
    priority = 0
    captured = state.board[move.to_square]
    moving = state.board[move.from_square]
    if captured and moving:
        priority += 100 + _piece_order(captured.type) - _piece_order(moving.type)
    if move.promotion is not None:
        priority += 90 + _piece_order(move.promotion)
    if move.kind is MoveKind.CASTLE:
        priority += 8
    return priority


def _piece_order(piece_type: PieceType) -> int:
    order = {
        PieceType.PAWN: 1,
        PieceType.KNIGHT: 3,
        PieceType.BISHOP: 3,
        PieceType.ROOK: 5,
        PieceType.QUEEN: 9,
        PieceType.KING: 20,
    }
    return order[piece_type]


def _model_evaluator_or_default(model_path: str | Path | None) -> Evaluator:
    path = Path(model_path or "models/value.pt").resolve()
    if not path.is_file():
        return evaluate_state
    stat = path.stat()
    cached = _MODEL_EVALUATOR_CACHE.get(path)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]
    try:
        from .value_model import load_value_evaluator

        evaluator = load_value_evaluator(path)
        _MODEL_EVALUATOR_CACHE[path] = (stat.st_mtime_ns, stat.st_size, evaluator)
        while len(_MODEL_EVALUATOR_CACHE) > MAX_CACHED_MODELS:
            _MODEL_EVALUATOR_CACHE.pop(next(iter(_MODEL_EVALUATOR_CACHE)))
        return evaluator
    except Exception:
        _MODEL_EVALUATOR_CACHE.pop(path, None)
        return evaluate_state


def clear_model_evaluator_cache() -> None:
    _MODEL_EVALUATOR_CACHE.clear()
