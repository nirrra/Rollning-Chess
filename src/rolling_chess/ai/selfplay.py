from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .search import Difficulty, choose_move
from ..moves import GameStatus
from ..pieces import Color
from ..state import GameState

DEFAULT_MAX_PLIES = 160
MAX_SELFPLAY_PLIES = 1024


@dataclass(frozen=True, slots=True)
class SelfPlaySummary:
    path: Path
    games: int
    samples: int


def generate_selfplay_games(
    games: int = 1,
    out_dir: str | Path = "data/selfplay",
    max_plies: int = DEFAULT_MAX_PLIES,
    difficulty: str | Difficulty = Difficulty.NORMAL,
    seed: int | None = None,
    opening_random_plies: int = 4,
) -> SelfPlaySummary:
    if games < 1:
        raise ValueError("games must be at least 1")
    if max_plies < 1:
        raise ValueError("max_plies must be at least 1")
    if max_plies > MAX_SELFPLAY_PLIES:
        raise ValueError(f"max_plies must be at most {MAX_SELFPLAY_PLIES}")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    target = out_path / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.jsonl"
    rng = random.Random(seed)
    level = Difficulty.from_value(difficulty) if isinstance(difficulty, str) else difficulty
    sample_count = 0

    with target.open("w", encoding="utf-8") as stream:
        for game_index in range(games):
            game_id = f"{target.stem}-{game_index + 1:04d}"
            samples = play_selfplay_game(
                game_id=game_id,
                max_plies=max_plies,
                difficulty=level,
                rng=rng,
                opening_random_plies=opening_random_plies,
            )
            for sample in samples:
                stream.write(json.dumps(sample, ensure_ascii=True, sort_keys=True))
                stream.write("\n")
            sample_count += len(samples)

    return SelfPlaySummary(path=target, games=games, samples=sample_count)


def play_selfplay_game(
    game_id: str,
    max_plies: int = DEFAULT_MAX_PLIES,
    difficulty: str | Difficulty = Difficulty.NORMAL,
    rng: random.Random | None = None,
    opening_random_plies: int = 4,
) -> list[dict[str, object]]:
    rng = rng or random.Random()
    level = Difficulty.from_value(difficulty) if isinstance(difficulty, str) else difficulty
    if max_plies < 1:
        raise ValueError("max_plies must be at least 1")
    if max_plies > MAX_SELFPLAY_PLIES:
        raise ValueError(f"max_plies must be at most {MAX_SELFPLAY_PLIES}")
    state = GameState.initial()
    samples: list[dict[str, object]] = []
    ply = 0

    while ply < max_plies and state.result().status is GameStatus.ONGOING:
        samples.append(
            {
                "state": state.to_dict(include_legal_moves=False),
                "turn": state.turn.value,
                "ply": ply,
                "game_id": game_id,
            }
        )
        move_level = Difficulty.EASY if ply < opening_random_plies else level
        move = choose_move(state, move_level, rng=rng)
        if move is None:
            break
        state = state.apply_move(move)
        ply += 1

    labels = _labels_for_finished_state(state, max_reached=ply >= max_plies)
    for sample in samples:
        sample["result"] = labels[Color(str(sample["turn"]))]
    return samples


def _labels_for_finished_state(
    state: GameState, max_reached: bool = False
) -> dict[Color, float]:
    result = state.result()
    if max_reached and result.status is GameStatus.ONGOING:
        return {Color.WHITE: 0.0, Color.BLACK: 0.0}
    if result.status is not GameStatus.CHECKMATE or result.winner is None:
        return {Color.WHITE: 0.0, Color.BLACK: 0.0}
    return {
        Color.WHITE: 1.0 if result.winner is Color.WHITE else -1.0,
        Color.BLACK: 1.0 if result.winner is Color.BLACK else -1.0,
    }
