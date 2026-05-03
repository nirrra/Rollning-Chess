from rolling_chess import Color

from .conftest import move_texts


def test_king_can_move_across_edge(position):
    state = position({"a4": "K", "e8": "k"})

    assert "a4h4" in move_texts(state)


def test_knight_can_jump_across_edge(position):
    state = position({"e1": "K", "e8": "k", "a4": "N"})
    moves = move_texts(state)

    assert {"a4h6", "a4h2", "a4g5", "a4g3"} <= moves


def test_rook_can_use_unblocked_wrapped_route(position):
    state = position({"e1": "K", "e8": "k", "a4": "R", "b4": "P"})

    assert "a4e4" in move_texts(state)


def test_rook_cannot_reach_when_both_horizontal_routes_are_blocked(position):
    state = position({"e1": "K", "e8": "k", "a4": "R", "b4": "P", "h4": "P"})

    assert "a4e4" not in move_texts(state)


def test_bishop_can_move_diagonally_across_edge(position):
    state = position({"d1": "K", "e8": "k", "a1": "B"})

    assert "a1h2" in move_texts(state)


def test_queen_combines_wrapped_rook_and_bishop_moves(position):
    state = position({"d1": "K", "e8": "k", "a1": "Q"})
    moves = move_texts(state)

    assert "a1h1" in moves
    assert "a1h2" in moves


def test_white_pawn_can_capture_across_edge(position):
    state = position({"e1": "K", "e8": "k", "a5": "P", "h6": "r"})

    assert "a5h6" in move_texts(state)


def test_black_pawn_can_capture_across_edge(position):
    state = position({"e1": "K", "e8": "k", "h4": "p", "a3": "R"}, turn=Color.BLACK)

    assert "h4a3" in move_texts(state)

