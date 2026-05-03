from __future__ import annotations

from collections.abc import Iterable

from .exceptions import InvalidSquareError
from .pieces import Color, Piece, PieceType

FILES = "abcdefgh"
RANKS = "12345678"
BOARD_SIZE = 64


def wrap_file(file_index: int) -> int:
    return file_index % 8


def is_rank_on_board(rank_index: int) -> bool:
    return 0 <= rank_index < 8


def make_square(file_index: int, rank_index: int) -> int:
    if not is_rank_on_board(rank_index):
        raise InvalidSquareError(f"rank is outside 1..8: {rank_index + 1}")
    return rank_index * 8 + wrap_file(file_index)


def file_of(square: int) -> int:
    return square % 8


def rank_of(square: int) -> int:
    return square // 8


def parse_square(value: str) -> int:
    if len(value) != 2:
        raise InvalidSquareError(f"invalid square: {value}")
    file_char, rank_char = value[0].lower(), value[1]
    if file_char not in FILES or rank_char not in RANKS:
        raise InvalidSquareError(f"invalid square: {value}")
    return make_square(FILES.index(file_char), RANKS.index(rank_char))


def square_name(square: int) -> str:
    if not 0 <= square < BOARD_SIZE:
        raise InvalidSquareError(f"invalid square index: {square}")
    return f"{FILES[file_of(square)]}{RANKS[rank_of(square)]}"


def offset_square(square: int, df: int, dr: int) -> int | None:
    rank = rank_of(square) + dr
    if not is_rank_on_board(rank):
        return None
    return make_square(file_of(square) + df, rank)


def iter_squares() -> Iterable[int]:
    return range(BOARD_SIZE)


def empty_board() -> tuple[Piece | None, ...]:
    return (None,) * BOARD_SIZE


def initial_board() -> tuple[Piece | None, ...]:
    board: list[Piece | None] = [None] * BOARD_SIZE
    order = [
        PieceType.ROOK,
        PieceType.KNIGHT,
        PieceType.BISHOP,
        PieceType.QUEEN,
        PieceType.KING,
        PieceType.BISHOP,
        PieceType.KNIGHT,
        PieceType.ROOK,
    ]
    for file_index, piece_type in enumerate(order):
        board[make_square(file_index, 0)] = Piece(Color.WHITE, piece_type)
        board[make_square(file_index, 7)] = Piece(Color.BLACK, piece_type)
        board[make_square(file_index, 1)] = Piece(Color.WHITE, PieceType.PAWN)
        board[make_square(file_index, 6)] = Piece(Color.BLACK, PieceType.PAWN)
    return tuple(board)


def ray_from(square: int, df: int, dr: int) -> list[int]:
    squares: list[int] = []
    max_steps = 7 if dr == 0 else 8
    for step in range(1, max_steps + 1):
        rank = rank_of(square) + dr * step
        if not is_rank_on_board(rank):
            break
        target = make_square(file_of(square) + df * step, rank)
        if target == square:
            break
        squares.append(target)
    return squares


def sliding_paths_between(
    source: int, target: int, directions: Iterable[tuple[int, int]]
) -> list[list[int]]:
    paths: list[list[int]] = []
    for df, dr in directions:
        path: list[int] = []
        for square in ray_from(source, df, dr):
            path.append(square)
            if square == target:
                paths.append(path)
                break
    return paths


def render_board(board: tuple[Piece | None, ...]) -> str:
    lines: list[str] = []
    for rank in range(7, -1, -1):
        pieces: list[str] = []
        for file_index in range(8):
            piece = board[make_square(file_index, rank)]
            pieces.append(piece.symbol if piece else ".")
        lines.append(f"{rank + 1} {' '.join(pieces)}")
    lines.append("  a b c d e f g h")
    return "\n".join(lines)

