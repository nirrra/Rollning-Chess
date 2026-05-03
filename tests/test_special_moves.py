from rolling_chess import Color, PieceType

from .conftest import move_texts


def test_cross_boundary_en_passant(position):
    state = position({"e1": "K", "e8": "k", "a5": "P", "h7": "p"}, turn=Color.BLACK)

    state = state.apply_move("h7h5")

    assert "a5h6" in move_texts(state)
    state = state.apply_move("a5h6")
    assert state.piece_at("h6").type is PieceType.PAWN
    assert state.piece_at("h5") is None


def test_standard_castling_is_available_but_no_extra_wrapped_castle(position):
    state = position(
        {"e1": "K", "a1": "R", "h1": "R", "e8": "k"},
        castling="KQ",
    )
    moves = move_texts(state)

    assert "e1g1" in moves
    assert "e1c1" in moves
    assert all(not move.startswith("e1a") for move in moves)
    assert all(not move.startswith("e1h") for move in moves)


def test_castling_uses_standard_empty_squares(position):
    state = position(
        {"e1": "K", "a1": "R", "h1": "R", "b1": "N", "e8": "k"},
        castling="KQ",
    )
    moves = move_texts(state)

    assert "e1g1" in moves
    assert "e1c1" not in moves


def test_pawn_promotion_requires_choice(position):
    state = position({"e1": "K", "e8": "k", "a7": "P"})
    moves = move_texts(state)

    assert {"a7a8q", "a7a8r", "a7a8b", "a7a8n"} <= moves
    assert "a7a8" not in moves

    promoted = state.apply_move("a7a8q")
    assert promoted.piece_at("a8").type is PieceType.QUEEN

