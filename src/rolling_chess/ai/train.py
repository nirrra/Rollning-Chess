from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .encoding import CHANNELS, state_to_planes
from .selfplay import DEFAULT_MAX_PLIES
from .value_model import build_value_model
from ..pieces import Color
from ..state import GameState


@dataclass(frozen=True, slots=True)
class TrainingSample:
    state: GameState
    result: float


@dataclass(frozen=True, slots=True)
class TrainingSummary:
    out_path: Path
    samples: int
    epochs: int
    final_loss: float


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    games: int
    model_wins: int
    normal_wins: int
    draws: int


def load_samples(data_dir: str | Path) -> list[TrainingSample]:
    return list(iter_samples(data_dir))


def iter_samples(data_dir: str | Path) -> Iterator[TrainingSample]:
    root = Path(data_dir)
    if not root.exists():
        raise ValueError(f"training data directory does not exist: {root}")
    found = False
    for path in sorted(root.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    found = True
                    yield _sample_from_payload(payload)
                except (TypeError, ValueError, KeyError) as exc:
                    raise ValueError(f"invalid sample in {path}:{line_number}: {exc}") from exc
    if not found:
        raise ValueError(f"no JSONL training samples found under {root}")


def train_value_model(
    data_dir: str | Path = "data/selfplay",
    out_path: str | Path = "models/value.pt",
    epochs: int = 5,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
) -> TrainingSummary:
    if epochs < 1:
        raise ValueError("epochs must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    torch = _require_torch()

    model = build_value_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = torch.nn.MSELoss()
    final_loss = 0.0
    sample_count = 0

    model.train()
    for _epoch in range(epochs):
        losses: list[float] = []
        batch: list[TrainingSample] = []
        epoch_samples = 0
        for sample in iter_samples(data_dir):
            batch.append(sample)
            epoch_samples += 1
            if len(batch) >= batch_size:
                losses.append(_train_batch(torch, model, optimizer, loss_fn, batch))
                batch = []
        if batch:
            losses.append(_train_batch(torch, model, optimizer, loss_fn, batch))
        if sample_count and sample_count != epoch_samples:
            raise ValueError("training sample count changed during training")
        sample_count = epoch_samples
        final_loss = sum(losses) / len(losses)

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "input_shape": [CHANNELS, 8, 8],
            "samples": sample_count,
            "epochs": epochs,
            "final_loss": final_loss,
        },
        target,
    )
    return TrainingSummary(
        out_path=target,
        samples=sample_count,
        epochs=epochs,
        final_loss=final_loss,
    )


def _train_batch(
    torch: Any,
    model: Any,
    optimizer: Any,
    loss_fn: Any,
    batch: list[TrainingSample],
) -> float:
    x = np.stack([state_to_planes(sample.state) for sample in batch])
    y = np.array([sample.result for sample in batch], dtype=np.float32)
    batch_x = torch.from_numpy(x).float()
    batch_y = torch.from_numpy(y).float()
    optimizer.zero_grad()
    predicted = model(batch_x)
    loss = loss_fn(predicted, batch_y)
    loss.backward()
    optimizer.step()
    return float(loss.item())


def evaluate_model_against_normal(
    model_path: str | Path = "models/value.pt",
    games: int = 20,
    max_plies: int = DEFAULT_MAX_PLIES,
) -> EvaluationSummary:
    from .search import Difficulty, choose_move
    from ..moves import GameStatus

    if games < 1:
        raise ValueError("games must be at least 1")
    model_wins = 0
    normal_wins = 0
    draws = 0
    model_path = Path(model_path)

    for game_index in range(games):
        model_color = Color.WHITE if game_index % 2 == 0 else Color.BLACK
        state = GameState.initial()
        ply = 0
        while ply < max_plies and state.result().status is GameStatus.ONGOING:
            level = Difficulty.EXPERIMENTAL if state.turn is model_color else Difficulty.NORMAL
            move = choose_move(state, level, model_path=model_path)
            if move is None:
                break
            state = state.apply_move(move)
            ply += 1
        result = state.result()
        if ply >= max_plies and result.status is GameStatus.ONGOING:
            draws += 1
        elif result.status is not GameStatus.CHECKMATE or result.winner is None:
            draws += 1
        elif result.winner is model_color:
            model_wins += 1
        else:
            normal_wins += 1

    return EvaluationSummary(
        games=games,
        model_wins=model_wins,
        normal_wins=normal_wins,
        draws=draws,
    )


def _sample_from_payload(payload: dict[str, Any]) -> TrainingSample:
    state_payload = payload["state"]
    result = float(payload["result"])
    if result not in {-1.0, 0.0, 1.0}:
        raise ValueError("result must be -1.0, 0.0, or 1.0")
    if payload.get("turn") not in {Color.WHITE.value, Color.BLACK.value}:
        raise ValueError("turn must be white or black")
    if not isinstance(state_payload, dict):
        raise ValueError("state must be an object")
    return TrainingSample(state=GameState.from_dict(state_payload), result=result)


def _require_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for training. Install the optional AI dependency first."
        ) from exc
    return torch
