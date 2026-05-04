from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .board import parse_square, square_name
from .exceptions import InvalidMoveFormatError, InvalidSquareError
from .pieces import Color, PieceType


class MoveKind(Enum):
    NORMAL = "normal"
    CASTLE = "castle"
    EN_PASSANT = "en_passant"
    PROMOTION = "promotion"


class GameStatus(Enum):
    ONGOING = "ongoing"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"


@dataclass(frozen=True, slots=True)
class GameResult:
    status: GameStatus
    winner: Color | None = None

    @property
    def is_over(self) -> bool:
        return self.status is not GameStatus.ONGOING


@dataclass(frozen=True, slots=True)
class MoveRecord:
    move: str
    from_square: str
    to_square: str
    piece: str | None = None
    piece_symbol: str | None = None
    promotion: str | None = None
    capture: str | None = None
    capture_symbol: str | None = None
    capture_kind: str | None = None

    @classmethod
    def from_move_text(cls, move: str) -> "MoveRecord":
        text = move.strip().lower()
        return cls(
            move=text,
            from_square=text[:2],
            to_square=text[2:4],
            promotion=text[4] if len(text) == 5 else None,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MoveRecord":
        move = data.get("move")
        if not isinstance(move, str):
            raise ValueError("history detail must include move")
        from_square = data.get("from", move[:2])
        to_square = data.get("to", move[2:4])
        if not isinstance(from_square, str) or not isinstance(to_square, str):
            raise ValueError("history detail from/to must be strings")
        piece = data.get("piece")
        piece_symbol = data.get("piece_symbol")
        promotion = data.get("promotion")
        capture = data.get("capture")
        capture_symbol = data.get("capture_symbol")
        capture_kind = data.get("capture_kind")
        return cls(
            move=move,
            from_square=from_square,
            to_square=to_square,
            piece=str(piece) if piece is not None else None,
            piece_symbol=str(piece_symbol) if piece_symbol is not None else None,
            promotion=str(promotion) if promotion is not None else None,
            capture=str(capture) if capture is not None else None,
            capture_symbol=str(capture_symbol) if capture_symbol is not None else None,
            capture_kind=str(capture_kind) if capture_kind is not None else None,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "move": self.move,
            "from": self.from_square,
            "to": self.to_square,
            "piece": self.piece,
            "piece_symbol": self.piece_symbol,
            "promotion": self.promotion,
            "capture": self.capture,
            "capture_symbol": self.capture_symbol,
            "capture_kind": self.capture_kind,
        }


@dataclass(frozen=True, slots=True)
class Move:
    from_square: int
    to_square: int
    promotion: PieceType | None = None
    kind: MoveKind = MoveKind.NORMAL

    @classmethod
    def from_uci(cls, value: str) -> "Move":
        text = value.strip().lower()
        if len(text) not in (4, 5):
            raise InvalidMoveFormatError(f"invalid move format: {value}")
        try:
            from_square = parse_square(text[:2])
            to_square = parse_square(text[2:4])
            promotion = (
                PieceType.from_promotion_char(text[4]) if len(text) == 5 else None
            )
        except (InvalidSquareError, ValueError) as exc:
            raise InvalidMoveFormatError(str(exc)) from exc
        return cls(from_square, to_square, promotion)

    def to_uci(self) -> str:
        promotion = self.promotion.value if self.promotion else ""
        return f"{square_name(self.from_square)}{square_name(self.to_square)}{promotion}"

    def matches(self, other: "Move") -> bool:
        return (
            self.from_square == other.from_square
            and self.to_square == other.to_square
            and self.promotion == other.promotion
        )

    def __str__(self) -> str:
        return self.to_uci()
