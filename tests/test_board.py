from rolling_chess.board import (
    file_of,
    offset_square,
    parse_square,
    rank_of,
    sliding_paths_between,
    square_name,
)
from rolling_chess.rules import BISHOP_DIRECTIONS


def test_files_wrap_but_ranks_do_not():
    a4 = parse_square("a4")
    h4 = parse_square("h4")

    assert offset_square(a4, -1, 0) == h4
    assert offset_square(h4, 1, 0) == a4
    assert offset_square(parse_square("a1"), 0, -1) is None
    assert offset_square(parse_square("h8"), 0, 1) is None


def test_square_names_round_trip():
    for name in ("a1", "h1", "a8", "h8", "e4"):
        square = parse_square(name)
        assert square_name(square) == name
        assert 0 <= file_of(square) < 8
        assert 0 <= rank_of(square) < 8


def test_bishop_path_can_cross_left_edge():
    paths = sliding_paths_between(parse_square("a1"), parse_square("h2"), BISHOP_DIRECTIONS)

    assert [[square_name(square) for square in path] for path in paths] == [["h2"]]

