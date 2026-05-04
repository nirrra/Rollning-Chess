from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .encoding import CHANNELS, state_to_tensor
from .evaluate import evaluate_state
from ..state import GameState

Evaluator = Callable[[GameState], float]


def build_value_model() -> Any:
    _torch, nn = _torch_modules()

    class ValueNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(CHANNELS, 48, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv2d(48, 64, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, 1)),
                nn.Flatten(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Tanh(),
            )

        def forward(self, x: Any) -> Any:
            return self.net(x).squeeze(-1)

    return ValueNet()


def load_value_evaluator(path: str | Path) -> Evaluator:
    torch, _nn = _torch_modules()
    model = build_value_model()
    checkpoint = torch.load(Path(path), map_location="cpu")
    state_dict = _state_dict_from_checkpoint(checkpoint)
    model.load_state_dict(state_dict)
    model.eval()

    def evaluator(state: GameState) -> float:
        try:
            with torch.no_grad():
                tensor = state_to_tensor(state).unsqueeze(0).float()
                return float(model(tensor).item()) * 1000.0
        except Exception:
            return evaluate_state(state)

    return evaluator


def _state_dict_from_checkpoint(checkpoint: object) -> object:
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            return checkpoint["model_state_dict"]
        if "state_dict" in checkpoint:
            return checkpoint["state_dict"]
    return checkpoint


def _torch_modules() -> tuple[Any, Any]:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for value model operations. "
            "Install the optional AI dependency before training or loading a model."
        ) from exc
    return torch, nn
