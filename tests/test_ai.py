from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

import pytest

from rolling_chess import Color, GameStatus, GameState
from rolling_chess.ai.encoding import encoded_state_summary, state_to_planes
from rolling_chess.ai.game import AIGameError, AIGameStore
from rolling_chess.ai.search import Difficulty, choose_move, clear_model_evaluator_cache
from rolling_chess.ai.selfplay import MAX_SELFPLAY_PLIES, generate_selfplay_games
from rolling_chess.ai.train import iter_samples, load_samples, train_value_model


@pytest.fixture
def workspace_tmp(request):
    path = Path(".pytest_tmp") / request.node.name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_easy_ai_is_seed_reproducible_and_legal():
    state = GameState.initial()

    first = choose_move(state, Difficulty.EASY, rng=random.Random(7))
    second = choose_move(state, Difficulty.EASY, rng=random.Random(7))

    assert first == second
    assert first in state.legal_moves()


def test_normal_ai_returns_legal_move_without_mutating_state():
    state = GameState.initial()
    before = state.to_dict(include_legal_moves=False)

    move = choose_move(state, Difficulty.NORMAL)

    assert move in state.legal_moves()
    assert state.to_dict(include_legal_moves=False) == before


def test_experimental_ai_falls_back_without_model():
    state = GameState.initial()

    move = choose_move(state, Difficulty.EXPERIMENTAL, model_path="missing-model.pt")

    assert move in state.legal_moves()


def test_experimental_ai_reuses_cached_model_evaluator(workspace_tmp, monkeypatch):
    model_path = workspace_tmp / "value.pt"
    model_path.write_bytes(b"fake model")
    calls = []

    from rolling_chess.ai import value_model

    def fake_load_value_evaluator(path):
        calls.append(path)
        return lambda _state: 0.0

    monkeypatch.setattr(value_model, "load_value_evaluator", fake_load_value_evaluator)
    clear_model_evaluator_cache()
    try:
        state = GameState.initial()
        choose_move(state, Difficulty.EXPERIMENTAL, model_path=model_path)
        choose_move(state, Difficulty.EXPERIMENTAL, model_path=model_path)
    finally:
        clear_model_evaluator_cache()

    assert calls == [model_path.resolve()]


def test_ai_returns_none_from_terminal_position(position):
    state = position(
        {"a1": "k", "c2": "K", "h3": "Q", "b3": "R"},
        turn=Color.BLACK,
    )

    assert state.result().status is GameStatus.STALEMATE
    assert choose_move(state, Difficulty.EASY) is None


def test_ai_store_rejects_player_move_when_it_is_ai_turn():
    store = AIGameStore()
    session = store.create_game("white", "easy")
    session.state = session.state.apply_move("e2e4")

    with pytest.raises(AIGameError, match="not player turn"):
        store.apply_player_move(session.game_id, "d2d4")


def test_ai_store_prunes_lru_games():
    store = AIGameStore(max_games=1, ttl_seconds=0)
    first = store.create_game("white", "easy")
    second = store.create_game("white", "easy")

    with pytest.raises(AIGameError, match="unknown AI game"):
        store.get_game(first.game_id)
    assert store.get_game(second.game_id).game_id == second.game_id


def test_state_encoding_shape_and_summary():
    state = GameState.initial()
    planes = state_to_planes(state)

    assert planes.shape == (18, 8, 8)
    assert planes.dtype.name == "float32"
    assert planes[:12].sum() == 32
    assert encoded_state_summary(state)["pieces"] == 32


def test_selfplay_writes_loadable_jsonl(workspace_tmp):
    summary = generate_selfplay_games(
        games=1,
        out_dir=workspace_tmp,
        max_plies=2,
        difficulty="easy",
        seed=3,
    )

    assert summary.path.exists()
    lines = summary.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == summary.samples == 2
    first = json.loads(lines[0])
    assert set(first) == {"game_id", "ply", "result", "state", "turn"}
    assert first["result"] in {-1.0, 0.0, 1.0}
    assert GameState.from_dict(first["state"]).turn.value == first["turn"]

    samples = load_samples(workspace_tmp)
    assert len(samples) == 2
    assert len(list(iter_samples(workspace_tmp))) == 2


def test_selfplay_rejects_unbounded_max_plies(workspace_tmp):
    with pytest.raises(ValueError, match="max_plies must be at most"):
        generate_selfplay_games(
            games=1,
            out_dir=workspace_tmp,
            max_plies=MAX_SELFPLAY_PLIES + 1,
            difficulty="easy",
        )


def test_train_command_behavior_with_optional_torch(workspace_tmp):
    summary = generate_selfplay_games(
        games=1,
        out_dir=workspace_tmp / "selfplay",
        max_plies=2,
        difficulty="easy",
        seed=5,
    )
    assert summary.samples == 2

    try:
        import torch  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="PyTorch is required"):
            train_value_model(workspace_tmp / "selfplay", workspace_tmp / "value.pt", epochs=1)
    else:
        trained = train_value_model(
            workspace_tmp / "selfplay",
            workspace_tmp / "value.pt",
            epochs=1,
            batch_size=2,
        )
        assert trained.out_path.exists()
        assert trained.samples == 2
