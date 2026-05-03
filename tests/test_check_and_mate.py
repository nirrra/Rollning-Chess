import pytest

from rolling_chess import Color, GameStatus, IllegalMoveError

from .conftest import move_texts


def test_wrapped_rook_attack_gives_check(position):
    state = position({"a4": "K", "e8": "k", "h4": "r"})

    assert state.is_check(Color.WHITE)


def test_legal_moves_filter_out_moves_that_leave_king_in_check(position):
    state = position({"e1": "K", "e8": "r", "a1": "R", "h8": "k"})

    assert "a1a2" not in move_texts(state)
    with pytest.raises(IllegalMoveError):
        state.apply_move("a1a2")


def test_fools_mate_sequence_ends_in_checkmate():
    state = __import__("rolling_chess").GameState.initial()

    for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
        state = state.apply_move(move)

    result = state.result()
    assert result.status is GameStatus.CHECKMATE
    assert result.winner is Color.BLACK


def test_constructed_stalemate(position):
    state = position(
        {"a1": "k", "c2": "K", "h3": "Q", "b3": "R"},
        turn=Color.BLACK,
    )

    assert not state.is_check(Color.BLACK)
    assert state.result().status is GameStatus.STALEMATE

