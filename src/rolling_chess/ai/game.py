from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock

from .search import Difficulty, choose_move
from ..exceptions import RollingChessError
from ..moves import GameStatus
from ..pieces import Color
from ..state import GameState


DEFAULT_AI_GAME_TTL_SECONDS = 6 * 60 * 60
DEFAULT_MAX_AI_GAMES = 128


class AIGameError(ValueError):
    """Expected AI game error that can be returned to API callers."""


@dataclass(slots=True)
class AIGameSession:
    game_id: str
    state: GameState
    player_color: Color
    ai_color: Color
    difficulty: Difficulty
    model_path: Path
    created_at: datetime
    updated_at: datetime
    last_ai_move: str | None = None
    model_status: str = "not_used"

    def snapshot(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "state": self.state.to_dict(),
            "player_color": self.player_color.value,
            "ai_color": self.ai_color.value,
            "difficulty": self.difficulty.value,
            "last_ai_move": self.last_ai_move,
            "model_status": self.model_status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AIGameMoveResult:
    session: AIGameSession
    player_state: GameState


class AIGameStore:
    def __init__(
        self,
        model_path: Path | str = "models/value.pt",
        max_games: int = DEFAULT_MAX_AI_GAMES,
        ttl_seconds: int = DEFAULT_AI_GAME_TTL_SECONDS,
    ) -> None:
        self._games: dict[str, AIGameSession] = {}
        self._lock = RLock()
        self.model_path = Path(model_path)
        self.max_games = max(1, max_games)
        self.ttl = timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None

    def create_game(self, player_color: str, difficulty: str) -> AIGameSession:
        with self._lock:
            self._prune_locked()
            color = _parse_color(player_color)
            ai_color = color.other()
            level = Difficulty.from_value(difficulty)
            now = datetime.now(timezone.utc)
            session = AIGameSession(
                game_id=uuid.uuid4().hex,
                state=GameState.initial(),
                player_color=color,
                ai_color=ai_color,
                difficulty=level,
                model_path=self.model_path,
                created_at=now,
                updated_at=now,
            )
            if session.state.turn is session.ai_color:
                self._apply_ai_move(session)
            self._games[session.game_id] = session
            self._prune_locked(exempt={session.game_id})
            return session

    def get_game(self, game_id: str) -> AIGameSession:
        with self._lock:
            session = self._active_session(game_id)
            if session is None:
                raise AIGameError("unknown AI game")
            session.updated_at = datetime.now(timezone.utc)
            return session

    def apply_player_move_only(self, game_id: str, move_text: str) -> AIGameSession:
        with self._lock:
            session = self.get_game(game_id)
            if session.state.result().is_over:
                raise AIGameError("game is over")
            if session.state.turn is not session.player_color:
                raise AIGameError("not player turn")
            try:
                session.state = session.state.apply_move(move_text)
            except RollingChessError as exc:
                raise AIGameError(str(exc)) from exc
            session.updated_at = datetime.now(timezone.utc)
            session.last_ai_move = None
            return session

    def apply_ai_move(self, game_id: str) -> AIGameSession:
        with self._lock:
            session = self.get_game(game_id)
            if session.state.result().is_over:
                return session
            if session.state.turn is not session.ai_color:
                raise AIGameError("not AI turn")
            self._apply_ai_move(session)
            return session

    def apply_player_move(self, game_id: str, move_text: str) -> AIGameMoveResult:
        with self._lock:
            session = self.apply_player_move_only(game_id, move_text)
            player_state = session.state
            if session.state.result().status is GameStatus.ONGOING:
                self._apply_ai_move(session)
            return AIGameMoveResult(session=session, player_state=player_state)

    def _apply_ai_move(self, session: AIGameSession) -> None:
        move = choose_move(
            session.state,
            session.difficulty,
            model_path=session.model_path,
        )
        if move is None:
            session.last_ai_move = None
            return
        session.state = session.state.apply_move(move)
        session.last_ai_move = move.to_uci()
        session.updated_at = datetime.now(timezone.utc)
        if session.difficulty is Difficulty.EXPERIMENTAL:
            session.model_status = "loaded" if session.model_path.is_file() else "fallback"
        else:
            session.model_status = "not_used"

    def prune(self) -> None:
        with self._lock:
            self._prune_locked()

    def _active_session(self, game_id: str) -> AIGameSession | None:
        session = self._games.get(game_id)
        if session is None:
            return None
        if self.ttl is not None and datetime.now(timezone.utc) - session.updated_at > self.ttl:
            self._games.pop(game_id, None)
            return None
        return session

    def _prune_locked(self, exempt: set[str] | None = None) -> None:
        exempt = exempt or set()
        now = datetime.now(timezone.utc)
        if self.ttl is not None:
            expired = [
                game_id
                for game_id, session in self._games.items()
                if game_id not in exempt and now - session.updated_at > self.ttl
            ]
            for game_id in expired:
                self._games.pop(game_id, None)

        overflow = len(self._games) - self.max_games
        if overflow <= 0:
            return
        candidates = sorted(
            (
                (game_id, session)
                for game_id, session in self._games.items()
                if game_id not in exempt
            ),
            key=lambda item: item[1].updated_at,
        )
        for game_id, _session in candidates[:overflow]:
            self._games.pop(game_id, None)


def _parse_color(value: str) -> Color:
    try:
        return Color(value.lower())
    except ValueError as exc:
        raise AIGameError(f"invalid player color: {value}") from exc
