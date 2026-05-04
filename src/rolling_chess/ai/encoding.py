from __future__ import annotations

from typing import Any

import numpy as np

from ..board import file_of, rank_of, square_name
from ..pieces import Color, PieceType
from ..state import GameState

CHANNELS = 18
BOARD_HEIGHT = 8
BOARD_WIDTH = 8

PIECE_PLANES: tuple[tuple[Color, PieceType], ...] = (
    (Color.WHITE, PieceType.KING),
    (Color.WHITE, PieceType.QUEEN),
    (Color.WHITE, PieceType.ROOK),
    (Color.WHITE, PieceType.BISHOP),
    (Color.WHITE, PieceType.KNIGHT),
    (Color.WHITE, PieceType.PAWN),
    (Color.BLACK, PieceType.KING),
    (Color.BLACK, PieceType.QUEEN),
    (Color.BLACK, PieceType.ROOK),
    (Color.BLACK, PieceType.BISHOP),
    (Color.BLACK, PieceType.KNIGHT),
    (Color.BLACK, PieceType.PAWN),
)

CASTLING_PLANES = ("K", "Q", "k", "q")


def state_to_planes(state: GameState) -> np.ndarray:
    planes = np.zeros((CHANNELS, BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
    piece_channels = {
        (color, piece_type): index
        for index, (color, piece_type) in enumerate(PIECE_PLANES)
    }

    for square, piece in enumerate(state.board):
        if piece is None:
            continue
        planes[piece_channels[(piece.color, piece.type)], rank_of(square), file_of(square)] = 1.0

    planes[12, :, :] = 1.0 if state.turn is Color.WHITE else 0.0
    for offset, right in enumerate(CASTLING_PLANES, start=13):
        if right in state.castling_rights:
            planes[offset, :, :] = 1.0

    if state.en_passant_target is not None:
        planes[17, rank_of(state.en_passant_target), file_of(state.en_passant_target)] = 1.0

    return planes


def state_to_tensor(state: GameState) -> Any:
    torch = _require_torch()
    return torch.from_numpy(state_to_planes(state))


def encoded_state_summary(state: GameState) -> dict[str, object]:
    """Small diagnostic helper used by CLI/debug tests without importing torch."""
    return {
        "shape": [CHANNELS, BOARD_HEIGHT, BOARD_WIDTH],
        "turn": state.turn.value,
        "pieces": len(state.to_dict(include_legal_moves=False)["pieces"]),
        "castling_rights": "".join(sorted(state.castling_rights)),
        "en_passant_target": square_name(state.en_passant_target)
        if state.en_passant_target is not None
        else None,
    }


def _require_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for tensor/model operations. "
            "Install the optional AI dependency before training."
        ) from exc
    return torch
