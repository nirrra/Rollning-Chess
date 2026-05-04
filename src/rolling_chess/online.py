from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from random import SystemRandom
from threading import RLock
from typing import Any

from .exceptions import RollingChessError
from .moves import Move
from .pieces import Color
from .state import GameState


DEFAULT_ROOM_TTL_SECONDS = 6 * 60 * 60
DEFAULT_MAX_ROOMS = 128


class RoomError(ValueError):
    """Expected room-level error that should be returned to the client."""


class RoomStatus(Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"


@dataclass(slots=True)
class OnlinePlayer:
    token: str
    nickname: str
    color: Color
    connected: bool = False
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_public_dict(self, viewer_token: str | None = None) -> dict[str, object]:
        return {
            "nickname": self.nickname,
            "color": self.color.value,
            "connected": self.connected,
            "last_seen": self.last_seen.isoformat(),
            "is_you": self.token == viewer_token,
        }


@dataclass(slots=True)
class OnlineRoom:
    room_id: str
    state: GameState
    players: dict[Color, OnlinePlayer]
    created_at: datetime
    updated_at: datetime
    version: int = 0
    status: RoomStatus = RoomStatus.WAITING
    connections: dict[str, Any] = field(default_factory=dict)

    def player_for_token(self, token: str) -> OnlinePlayer | None:
        return next((player for player in self.players.values() if player.token == token), None)

    def available_color(self) -> Color | None:
        for color in (Color.WHITE, Color.BLACK):
            if color not in self.players:
                return color
        return None

    def add_player(self, nickname: str, color: Color) -> OnlinePlayer:
        player = OnlinePlayer(token=_token(), nickname=_clean_nickname(nickname), color=color)
        self.players[color] = player
        self._refresh_status()
        self.touch()
        return player

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def _refresh_status(self) -> None:
        if self.state.result().is_over:
            self.status = RoomStatus.FINISHED
        elif len(self.players) == 2:
            self.status = RoomStatus.ACTIVE
        else:
            self.status = RoomStatus.WAITING

    def snapshot(self, viewer_token: str | None = None) -> dict[str, object]:
        self._refresh_status()
        players: dict[str, object] = {}
        for color in (Color.WHITE, Color.BLACK):
            player = self.players.get(color)
            players[color.value] = player.to_public_dict(viewer_token) if player else None
        viewer = self.player_for_token(viewer_token) if viewer_token else None
        return {
            "room_id": self.room_id,
            "version": self.version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "viewer_color": viewer.color.value if viewer else None,
            "state": self.state.to_dict(),
            "players": players,
        }


class OnlineRoomStore:
    def __init__(
        self,
        max_rooms: int = DEFAULT_MAX_ROOMS,
        ttl_seconds: int = DEFAULT_ROOM_TTL_SECONDS,
    ) -> None:
        self._rooms: dict[str, OnlineRoom] = {}
        self._lock = RLock()
        self.max_rooms = max(1, max_rooms)
        self.ttl = timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None

    def create_room(self, nickname: str) -> tuple[OnlineRoom, OnlinePlayer]:
        with self._lock:
            self._prune_locked()
            room_id = self._new_room_id()
            now = datetime.now(timezone.utc)
            color = _random.choice([Color.WHITE, Color.BLACK])
            room = OnlineRoom(
                room_id=room_id,
                state=GameState.initial(),
                players={},
                created_at=now,
                updated_at=now,
            )
            player = room.add_player(nickname, color)
            self._rooms[room_id] = room
            self._prune_locked(exempt={room_id})
            return room, player

    def join_room(
        self, room_id: str, nickname: str, player_token: str | None = None
    ) -> tuple[OnlineRoom, OnlinePlayer]:
        with self._lock:
            self._prune_locked()
            room = self._room_or_error(room_id)
            if player_token:
                player = room.player_for_token(player_token)
                if player:
                    player.nickname = _clean_nickname(nickname) or player.nickname
                    player.last_seen = datetime.now(timezone.utc)
                    room.touch()
                    return room, player
            color = room.available_color()
            if color is None:
                raise RoomError("room is full")
            player = room.add_player(nickname, color)
            return room, player

    def get_room(self, room_id: str) -> OnlineRoom:
        with self._lock:
            self._prune_locked()
            return self._room_or_error(room_id)

    def connect(self, room_id: str, token: str, connection: Any) -> OnlineRoom:
        with self._lock:
            self._prune_locked()
            room = self._room_or_error(room_id)
            player = room.player_for_token(token)
            if player is None:
                raise RoomError("unknown player token")
            player.connected = True
            player.last_seen = datetime.now(timezone.utc)
            room.connections[token] = connection
            room.touch()
            return room

    def disconnect(self, room_id: str, token: str) -> OnlineRoom | None:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return None
            player = room.player_for_token(token)
            if player is None:
                return room
            player.connected = False
            player.last_seen = datetime.now(timezone.utc)
            room.connections.pop(token, None)
            room.touch()
            self._prune_locked()
            return room

    def apply_move(self, room_id: str, token: str, move_text: str, version: int) -> OnlineRoom:
        with self._lock:
            self._prune_locked()
            room = self._room_or_error(room_id)
            player = room.player_for_token(token)
            if player is None:
                raise RoomError("unknown player token")
            if version != room.version:
                raise RoomError("stale room version")
            if player.color is not room.state.turn:
                raise RoomError("not your turn")
            try:
                move = Move.from_uci(move_text)
                moving_piece = room.state.piece_at(move.from_square)
            except (ValueError, IndexError) as exc:
                raise RoomError("invalid move format") from exc
            if moving_piece is None:
                raise RoomError("no piece on source square")
            if moving_piece.color is not player.color:
                raise RoomError("cannot move opponent piece")
            try:
                room.state = room.state.apply_move(move)
            except RollingChessError as exc:
                raise RoomError(str(exc)) from exc
            room.version += 1
            room.touch()
            room._refresh_status()
            return room

    def prune(self) -> None:
        with self._lock:
            self._prune_locked()

    def _room_or_error(self, room_id: str) -> OnlineRoom:
        room = self._rooms.get(room_id.upper())
        if room is None:
            raise RoomError("room not found")
        return room

    def _prune_locked(self, exempt: set[str] | None = None) -> None:
        exempt = exempt or set()
        now = datetime.now(timezone.utc)
        if self.ttl is not None:
            expired = [
                room_id
                for room_id, room in self._rooms.items()
                if room_id not in exempt and not room.connections and now - room.updated_at > self.ttl
            ]
            for room_id in expired:
                self._rooms.pop(room_id, None)

        overflow = len(self._rooms) - self.max_rooms
        if overflow <= 0:
            return
        candidates = sorted(
            (
                (room_id, room)
                for room_id, room in self._rooms.items()
                if room_id not in exempt and not room.connections
            ),
            key=lambda item: item[1].updated_at,
        )
        for room_id, _room in candidates[:overflow]:
            self._rooms.pop(room_id, None)

    def _new_room_id(self) -> str:
        for _ in range(100):
            room_id = "".join(_random.choice(_room_alphabet) for _ in range(6))
            if room_id not in self._rooms:
                return room_id
        raise RuntimeError("could not allocate room id")


def _clean_nickname(nickname: str) -> str:
    cleaned = nickname.strip()
    return cleaned[:24] if cleaned else "Player"


def _token() -> str:
    return secrets.token_urlsafe(24)


_random = SystemRandom()
_room_alphabet = string.ascii_uppercase + string.digits
