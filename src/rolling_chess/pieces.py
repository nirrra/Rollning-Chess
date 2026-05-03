from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Color(Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def forward(self) -> int:
        return 1 if self is Color.WHITE else -1

    @property
    def home_rank(self) -> int:
        return 0 if self is Color.WHITE else 7

    @property
    def pawn_start_rank(self) -> int:
        return 1 if self is Color.WHITE else 6

    @property
    def promotion_rank(self) -> int:
        return 7 if self is Color.WHITE else 0

    def other(self) -> "Color":
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class PieceType(Enum):
    KING = "k"
    QUEEN = "q"
    ROOK = "r"
    BISHOP = "b"
    KNIGHT = "n"
    PAWN = "p"

    @classmethod
    def from_promotion_char(cls, value: str) -> "PieceType":
        lookup = {
            "q": cls.QUEEN,
            "r": cls.ROOK,
            "b": cls.BISHOP,
            "n": cls.KNIGHT,
        }
        try:
            return lookup[value.lower()]
        except KeyError as exc:
            raise ValueError(f"invalid promotion piece: {value}") from exc


@dataclass(frozen=True, slots=True)
class Piece:
    color: Color
    type: PieceType

    @property
    def symbol(self) -> str:
        symbol = self.type.value
        return symbol.upper() if self.color is Color.WHITE else symbol

