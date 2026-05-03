from __future__ import annotations

import pytest

from rolling_chess import Color, GameState, Piece, PieceType


def piece(symbol: str) -> Piece:
    color = Color.WHITE if symbol.isupper() else Color.BLACK
    lookup = {
        "k": PieceType.KING,
        "q": PieceType.QUEEN,
        "r": PieceType.ROOK,
        "b": PieceType.BISHOP,
        "n": PieceType.KNIGHT,
        "p": PieceType.PAWN,
    }
    return Piece(color, lookup[symbol.lower()])


@pytest.fixture
def position():
    def build(
        pieces: dict[str, str],
        turn: Color = Color.WHITE,
        castling: str = "",
        en_passant: str | None = None,
    ) -> GameState:
        state = GameState.empty(turn=turn)
        state = GameState(
            board=state.board,
            turn=turn,
            castling_rights=frozenset(castling),
            en_passant_target=None,
            halfmove_clock=0,
            fullmove_number=1,
            history=(),
        )
        if en_passant:
            from rolling_chess.board import parse_square

            state = GameState(
                board=state.board,
                turn=state.turn,
                castling_rights=state.castling_rights,
                en_passant_target=parse_square(en_passant),
                halfmove_clock=state.halfmove_clock,
                fullmove_number=state.fullmove_number,
                history=state.history,
            )
        for square, symbol in pieces.items():
            state = state.with_piece(square, piece(symbol))
        return state

    return build


def move_texts(state: GameState) -> set[str]:
    return {move.to_uci() for move in state.legal_moves()}

