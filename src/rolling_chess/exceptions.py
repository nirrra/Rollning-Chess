class RollingChessError(Exception):
    """Base exception for rolling chess errors."""


class InvalidSquareError(RollingChessError):
    """Raised when a square is outside a1..h8."""


class InvalidMoveFormatError(RollingChessError):
    """Raised when move text cannot be parsed."""


class IllegalMoveError(RollingChessError):
    """Raised when a well-formed move is illegal in the current state."""


class GameOverError(RollingChessError):
    """Raised when a move is attempted after the game is over."""

