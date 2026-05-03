from __future__ import annotations

from .board import (
    file_of,
    iter_squares,
    make_square,
    offset_square,
    parse_square,
    rank_of,
    ray_from,
    sliding_paths_between,
)
from .moves import Move, MoveKind
from .pieces import Color, Piece, PieceType
from .state import GameState

ROOK_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))
BISHOP_DIRECTIONS = ((1, 1), (-1, 1), (1, -1), (-1, -1))
QUEEN_DIRECTIONS = ROOK_DIRECTIONS + BISHOP_DIRECTIONS
KNIGHT_OFFSETS = (
    (1, 2),
    (2, 1),
    (-1, 2),
    (-2, 1),
    (1, -2),
    (2, -1),
    (-1, -2),
    (-2, -1),
)
KING_OFFSETS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (-1, 1),
    (1, -1),
    (-1, -1),
)
PROMOTIONS = (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT)


def legal_moves(state: GameState) -> tuple[Move, ...]:
    moves: list[Move] = []
    for move in pseudo_legal_moves(state, state.turn):
        next_state = state._apply_unchecked(move)
        if not is_in_check(next_state, state.turn):
            moves.append(move)
    return tuple(_dedupe_moves(moves))


def pseudo_legal_moves(state: GameState, color: Color) -> tuple[Move, ...]:
    moves: list[Move] = []
    for square in iter_squares():
        piece = state.board[square]
        if piece is None or piece.color is not color:
            continue
        if piece.type is PieceType.PAWN:
            moves.extend(_pawn_moves(state, square, piece))
        elif piece.type is PieceType.KNIGHT:
            moves.extend(_jump_moves(state, square, piece, KNIGHT_OFFSETS))
        elif piece.type is PieceType.BISHOP:
            moves.extend(_sliding_moves(state, square, piece, BISHOP_DIRECTIONS))
        elif piece.type is PieceType.ROOK:
            moves.extend(_sliding_moves(state, square, piece, ROOK_DIRECTIONS))
        elif piece.type is PieceType.QUEEN:
            moves.extend(_sliding_moves(state, square, piece, QUEEN_DIRECTIONS))
        elif piece.type is PieceType.KING:
            moves.extend(_jump_moves(state, square, piece, KING_OFFSETS))
            moves.extend(_castle_moves(state, square, piece))
    return tuple(_dedupe_moves(moves))


def is_in_check(state: GameState, color: Color) -> bool:
    king_square = _find_king(state, color)
    if king_square is None:
        return False
    return is_square_attacked(state, king_square, color.other())


def is_square_attacked(state: GameState, square: int, by_color: Color) -> bool:
    for attacker_square, piece in enumerate(state.board):
        if piece is None or piece.color is not by_color:
            continue
        if _piece_attacks_square(state, attacker_square, piece, square):
            return True
    return False


def _pawn_moves(state: GameState, square: int, piece: Piece) -> list[Move]:
    moves: list[Move] = []
    one = offset_square(square, 0, piece.color.forward)
    if one is not None and state.board[one] is None:
        moves.extend(_pawn_advance_moves(square, one, piece))
        if rank_of(square) == piece.color.pawn_start_rank:
            two = offset_square(square, 0, piece.color.forward * 2)
            if two is not None and state.board[two] is None:
                moves.append(Move(square, two))

    for df in (-1, 1):
        target = offset_square(square, df, piece.color.forward)
        if target is None:
            continue
        occupant = state.board[target]
        if occupant is not None and occupant.color is not piece.color:
            moves.extend(_pawn_capture_moves(square, target, piece))
        elif target == state.en_passant_target and _has_en_passant_victim(state, square, target, piece):
            moves.append(Move(square, target, kind=MoveKind.EN_PASSANT))
    return moves


def _pawn_advance_moves(source: int, target: int, piece: Piece) -> list[Move]:
    if rank_of(target) != piece.color.promotion_rank:
        return [Move(source, target)]
    return [Move(source, target, promotion, MoveKind.PROMOTION) for promotion in PROMOTIONS]


def _pawn_capture_moves(source: int, target: int, piece: Piece) -> list[Move]:
    if rank_of(target) != piece.color.promotion_rank:
        return [Move(source, target)]
    return [Move(source, target, promotion, MoveKind.PROMOTION) for promotion in PROMOTIONS]


def _has_en_passant_victim(state: GameState, source: int, target: int, piece: Piece) -> bool:
    victim_square = make_square(file_of(target), rank_of(source))
    victim = state.board[victim_square]
    return (
        victim is not None
        and victim.color is piece.color.other()
        and victim.type is PieceType.PAWN
    )


def _jump_moves(
    state: GameState, square: int, piece: Piece, offsets: tuple[tuple[int, int], ...]
) -> list[Move]:
    moves: list[Move] = []
    seen: set[int] = set()
    for df, dr in offsets:
        target = offset_square(square, df, dr)
        if target is None or target in seen:
            continue
        seen.add(target)
        occupant = state.board[target]
        if occupant is None or occupant.color is not piece.color:
            moves.append(Move(square, target))
    return moves


def _sliding_moves(
    state: GameState, square: int, piece: Piece, directions: tuple[tuple[int, int], ...]
) -> list[Move]:
    moves: list[Move] = []
    for df, dr in directions:
        for target in ray_from(square, df, dr):
            occupant = state.board[target]
            if occupant is None:
                moves.append(Move(square, target))
                continue
            if occupant.color is not piece.color:
                moves.append(Move(square, target))
            break
    return moves


def _castle_moves(state: GameState, square: int, piece: Piece) -> list[Move]:
    if piece.type is not PieceType.KING:
        return []
    if square != make_square(4, piece.color.home_rank):
        return []
    if is_square_attacked(state, square, piece.color.other()):
        return []

    moves: list[Move] = []
    rank = piece.color.home_rank
    if _can_castle_kingside(state, piece.color, rank):
        moves.append(Move(square, make_square(6, rank), kind=MoveKind.CASTLE))
    if _can_castle_queenside(state, piece.color, rank):
        moves.append(Move(square, make_square(2, rank), kind=MoveKind.CASTLE))
    return moves


def _can_castle_kingside(state: GameState, color: Color, rank: int) -> bool:
    right = "K" if color is Color.WHITE else "k"
    if right not in state.castling_rights:
        return False
    rook_square = make_square(7, rank)
    rook = state.board[rook_square]
    if rook != Piece(color, PieceType.ROOK):
        return False
    if state.board[make_square(5, rank)] is not None or state.board[make_square(6, rank)] is not None:
        return False
    return not (
        is_square_attacked(state, make_square(5, rank), color.other())
        or is_square_attacked(state, make_square(6, rank), color.other())
    )


def _can_castle_queenside(state: GameState, color: Color, rank: int) -> bool:
    right = "Q" if color is Color.WHITE else "q"
    if right not in state.castling_rights:
        return False
    rook_square = make_square(0, rank)
    rook = state.board[rook_square]
    if rook != Piece(color, PieceType.ROOK):
        return False
    for file_index in (1, 2, 3):
        if state.board[make_square(file_index, rank)] is not None:
            return False
    return not (
        is_square_attacked(state, make_square(3, rank), color.other())
        or is_square_attacked(state, make_square(2, rank), color.other())
    )


def _piece_attacks_square(
    state: GameState, attacker_square: int, piece: Piece, target: int
) -> bool:
    if piece.type is PieceType.PAWN:
        for df in (-1, 1):
            if offset_square(attacker_square, df, piece.color.forward) == target:
                return True
        return False
    if piece.type is PieceType.KNIGHT:
        return any(offset_square(attacker_square, df, dr) == target for df, dr in KNIGHT_OFFSETS)
    if piece.type is PieceType.KING:
        return any(offset_square(attacker_square, df, dr) == target for df, dr in KING_OFFSETS)
    if piece.type is PieceType.ROOK:
        return _has_clear_sliding_attack(state, attacker_square, target, ROOK_DIRECTIONS)
    if piece.type is PieceType.BISHOP:
        return _has_clear_sliding_attack(state, attacker_square, target, BISHOP_DIRECTIONS)
    if piece.type is PieceType.QUEEN:
        return _has_clear_sliding_attack(state, attacker_square, target, QUEEN_DIRECTIONS)
    return False


def _has_clear_sliding_attack(
    state: GameState,
    attacker_square: int,
    target: int,
    directions: tuple[tuple[int, int], ...],
) -> bool:
    for path in sliding_paths_between(attacker_square, target, directions):
        blockers = path[:-1]
        if all(state.board[square] is None for square in blockers):
            return True
    return False


def _find_king(state: GameState, color: Color) -> int | None:
    for square, piece in enumerate(state.board):
        if piece == Piece(color, PieceType.KING):
            return square
    return None


def _dedupe_moves(moves: list[Move]) -> list[Move]:
    deduped: dict[tuple[int, int, PieceType | None, MoveKind], Move] = {}
    for move in moves:
        deduped[(move.from_square, move.to_square, move.promotion, move.kind)] = move
    return list(deduped.values())

