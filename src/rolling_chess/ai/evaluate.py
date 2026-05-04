from __future__ import annotations

from ..moves import GameStatus
from ..pieces import Color, PieceType
from ..state import GameState

MATE_SCORE = 100_000

PIECE_VALUES = {
    PieceType.KING: 0,
    PieceType.QUEEN: 900,
    PieceType.ROOK: 500,
    PieceType.BISHOP: 330,
    PieceType.KNIGHT: 320,
    PieceType.PAWN: 100,
}


def evaluate_state(state: GameState) -> float:
    """Return a deterministic score from the side-to-move perspective."""
    result = state.result()
    if result.status is GameStatus.CHECKMATE:
        return -MATE_SCORE if result.winner is state.turn.other() else MATE_SCORE
    if result.status is GameStatus.STALEMATE:
        return 0.0

    return static_evaluate_state(state)


def static_evaluate_state(state: GameState) -> float:
    white_score = _material_score(state) + _pawn_progress_score(state)
    return float(white_score if state.turn is Color.WHITE else -white_score)


def material_score_for_color(state: GameState, color: Color) -> int:
    score = 0
    for piece in state.board:
        if piece is None:
            continue
        value = PIECE_VALUES[piece.type]
        score += value if piece.color is color else -value
    return score


def _material_score(state: GameState) -> int:
    score = 0
    for piece in state.board:
        if piece is None:
            continue
        value = PIECE_VALUES[piece.type]
        score += value if piece.color is Color.WHITE else -value
    return score


def _pawn_progress_score(state: GameState) -> int:
    from ..board import rank_of

    score = 0
    for square, piece in enumerate(state.board):
        if piece is None or piece.type is not PieceType.PAWN:
            continue
        rank = rank_of(square)
        if piece.color is Color.WHITE:
            score += rank * 8
        else:
            score -= (7 - rank) * 8
    return score

