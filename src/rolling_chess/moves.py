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
