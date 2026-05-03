from __future__ import annotations

from dataclasses import dataclass, replace

from .board import (
    empty_board,
    file_of,
    initial_board,
    make_square,
    parse_square,
    rank_of,
    render_board,
    square_name,
)
from .exceptions import GameOverError, IllegalMoveError
from .moves import GameResult, GameStatus, Move, MoveKind, MoveRecord
from .pieces import Color, Piece, PieceType


@dataclass(frozen=True, slots=True)
class GameState:
    board: tuple[Piece | None, ...]
    turn: Color = Color.WHITE
    castling_rights: frozenset[str] = frozenset({"K", "Q", "k", "q"})
    en_passant_target: int | None = None
    halfmove_clock: int = 0
    fullmove_number: int = 1
    history: tuple[str, ...] = ()
    history_details: tuple[MoveRecord, ...] = ()

    @classmethod
    def initial(cls) -> "GameState":
        return cls(board=initial_board())

    @classmethod
    def empty(cls, turn: Color = Color.WHITE) -> "GameState":
        return cls(board=empty_board(), turn=turn, castling_rights=frozenset())

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "GameState":
        pieces = data.get("pieces")
        if not isinstance(pieces, dict):
            raise ValueError("state must include pieces")

        board: list[Piece | None] = list(empty_board())
        for square, symbol in pieces.items():
            if not isinstance(square, str) or not isinstance(symbol, str):
                raise ValueError("pieces must map square strings to piece symbols")
            board[parse_square(square)] = _piece_from_symbol(symbol)

        turn_value = data.get("turn", Color.WHITE.value)
        if not isinstance(turn_value, str):
            raise ValueError("turn must be a string")
        castling_value = data.get("castling_rights", "")
        if not isinstance(castling_value, str):
            raise ValueError("castling_rights must be a string")
        en_passant_value = data.get("en_passant_target")
        if en_passant_value is not None and not isinstance(en_passant_value, str):
            raise ValueError("en_passant_target must be a string or null")
        history_value = data.get("history", [])
        if not isinstance(history_value, list):
            raise ValueError("history must be a list")
        history_details_value = data.get("history_details")
        if history_details_value is not None and not isinstance(history_details_value, list):
            raise ValueError("history_details must be a list")
        if history_details_value is None:
            history_details = tuple(MoveRecord.from_move_text(str(move)) for move in history_value)
        else:
            details: list[MoveRecord] = []
            for item in history_details_value:
                if not isinstance(item, dict):
                    raise ValueError("history_details items must be objects")
                details.append(MoveRecord.from_dict(item))
            history_details = tuple(details)

        return cls(
            board=tuple(board),
            turn=Color(turn_value),
            castling_rights=frozenset(castling_value),
            en_passant_target=parse_square(en_passant_value) if en_passant_value else None,
            halfmove_clock=int(data.get("halfmove_clock", 0)),
            fullmove_number=int(data.get("fullmove_number", 1)),
            history=tuple(str(move) for move in history_value),
            history_details=history_details,
        )

    def with_piece(self, square: str | int, piece: Piece | None) -> "GameState":
        index = parse_square(square) if isinstance(square, str) else square
        board = list(self.board)
        board[index] = piece
        return replace(self, board=tuple(board))

    def piece_at(self, square: str | int) -> Piece | None:
        index = parse_square(square) if isinstance(square, str) else square
        return self.board[index]

    def legal_moves(self) -> tuple[Move, ...]:
        from .rules import legal_moves

        return legal_moves(self)

    def is_check(self, color: Color | None = None) -> bool:
        from .rules import is_in_check

        return is_in_check(self, color or self.turn)

    def result(self) -> GameResult:
        legal = self.legal_moves()
        if legal:
            return GameResult(GameStatus.ONGOING)
        if self.is_check(self.turn):
            return GameResult(GameStatus.CHECKMATE, self.turn.other())
        return GameResult(GameStatus.STALEMATE)

    def apply_move(self, move: Move | str) -> "GameState":
        requested = Move.from_uci(move) if isinstance(move, str) else move
        if self.result().is_over:
            raise GameOverError("cannot move after the game is over")
        for legal_move in self.legal_moves():
            if legal_move.matches(requested):
                return self._apply_unchecked(legal_move)
        raise IllegalMoveError(f"illegal move: {requested.to_uci()}")

    def _apply_unchecked(self, move: Move) -> "GameState":
        moving_piece = self.board[move.from_square]
        if moving_piece is None:
            raise IllegalMoveError(f"no piece on {square_name(move.from_square)}")

        board = list(self.board)
        captured_piece = board[move.to_square]
        board[move.from_square] = None

        if move.kind is MoveKind.EN_PASSANT:
            captured_square = make_square(file_of(move.to_square), rank_of(move.from_square))
            captured_piece = board[captured_square]
            board[captured_square] = None

        placed_piece = moving_piece
        if move.promotion is not None:
            placed_piece = Piece(moving_piece.color, move.promotion)

        board[move.to_square] = placed_piece

        if move.kind is MoveKind.CASTLE:
            self._apply_castle_rook_move(board, move)

        castling_rights = self._updated_castling_rights(move, moving_piece, captured_piece)
        en_passant_target = self._next_en_passant_target(move, moving_piece)
        halfmove_clock = 0 if moving_piece.type is PieceType.PAWN or captured_piece else self.halfmove_clock + 1
        fullmove_number = self.fullmove_number + (1 if self.turn is Color.BLACK else 0)
        move_record = self._move_record(move, captured_piece)

        return GameState(
            board=tuple(board),
            turn=self.turn.other(),
            castling_rights=castling_rights,
            en_passant_target=en_passant_target,
            halfmove_clock=halfmove_clock,
            fullmove_number=fullmove_number,
            history=self.history + (move.to_uci(),),
            history_details=self.history_details + (move_record,),
        )

    def _apply_castle_rook_move(self, board: list[Piece | None], move: Move) -> None:
        rank = rank_of(move.from_square)
        if file_of(move.to_square) == 6:
            rook_from = make_square(7, rank)
            rook_to = make_square(5, rank)
        else:
            rook_from = make_square(0, rank)
            rook_to = make_square(3, rank)
        board[rook_to] = board[rook_from]
        board[rook_from] = None

    def _updated_castling_rights(
        self, move: Move, moving_piece: Piece, captured_piece: Piece | None
    ) -> frozenset[str]:
        rights = set(self.castling_rights)
        if moving_piece.type is PieceType.KING:
            rights.difference_update({"K", "Q"} if moving_piece.color is Color.WHITE else {"k", "q"})
        if moving_piece.type is PieceType.ROOK:
            self._discard_rook_right(rights, move.from_square)
        if captured_piece and captured_piece.type is PieceType.ROOK:
            self._discard_rook_right(rights, move.to_square)
        return frozenset(rights)

    @staticmethod
    def _discard_rook_right(rights: set[str], square: int) -> None:
        if square == parse_square("h1"):
            rights.discard("K")
        elif square == parse_square("a1"):
            rights.discard("Q")
        elif square == parse_square("h8"):
            rights.discard("k")
        elif square == parse_square("a8"):
            rights.discard("q")

    @staticmethod
    def _next_en_passant_target(move: Move, moving_piece: Piece) -> int | None:
        if moving_piece.type is not PieceType.PAWN:
            return None
        if abs(rank_of(move.to_square) - rank_of(move.from_square)) != 2:
            return None
        middle_rank = (rank_of(move.to_square) + rank_of(move.from_square)) // 2
        return make_square(file_of(move.from_square), middle_rank)

    @staticmethod
    def _move_record(move: Move, captured_piece: Piece | None) -> MoveRecord:
        return MoveRecord(
            move=move.to_uci(),
            from_square=square_name(move.from_square),
            to_square=square_name(move.to_square),
            promotion=move.promotion.value if move.promotion else None,
            capture=captured_piece.type.value if captured_piece else None,
            capture_symbol=captured_piece.symbol if captured_piece else None,
            capture_kind="en_passant"
            if captured_piece and move.kind is MoveKind.EN_PASSANT
            else ("normal" if captured_piece else None),
        )

    def to_dict(self, include_legal_moves: bool = True) -> dict[str, object]:
        pieces: dict[str, str] = {}
        for index, piece in enumerate(self.board):
            if piece:
                pieces[square_name(index)] = piece.symbol
        result = self.result()
        data: dict[str, object] = {
            "pieces": pieces,
            "turn": self.turn.value,
            "castling_rights": "".join(sorted(self.castling_rights)),
            "en_passant_target": square_name(self.en_passant_target)
            if self.en_passant_target is not None
            else None,
            "halfmove_clock": self.halfmove_clock,
            "fullmove_number": self.fullmove_number,
            "history": list(self.history),
            "history_details": [record.to_dict() for record in self.history_details],
            "is_check": self.is_check(self.turn),
            "result": {
                "status": result.status.value,
                "winner": result.winner.value if result.winner else None,
            },
        }
        if include_legal_moves:
            data["legal_moves"] = [move.to_uci() for move in self.legal_moves()]
        return data

    def __str__(self) -> str:
        return render_board(self.board)


def _piece_from_symbol(symbol: str) -> Piece:
    if len(symbol) != 1:
        raise ValueError(f"invalid piece symbol: {symbol}")
    color = Color.WHITE if symbol.isupper() else Color.BLACK
    lookup = {
        "k": PieceType.KING,
        "q": PieceType.QUEEN,
        "r": PieceType.ROOK,
        "b": PieceType.BISHOP,
        "n": PieceType.KNIGHT,
        "p": PieceType.PAWN,
    }
    try:
        piece_type = lookup[symbol.lower()]
    except KeyError as exc:
        raise ValueError(f"invalid piece symbol: {symbol}") from exc
    return Piece(color, piece_type)
