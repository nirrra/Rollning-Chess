from __future__ import annotations

import argparse
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from .ai.game import AIGameError, AIGameStore
from .exceptions import RollingChessError
from .online import OnlineRoom, OnlineRoomStore, RoomError
from .state import GameState


DEFAULT_GAME_TTL_SECONDS = 6 * 60 * 60
DEFAULT_MAX_GAME_SESSIONS = 128
DEFAULT_MAX_UNDO_STATES = 257
DEFAULT_MAX_IMPORT_HISTORY = 512


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GameSession:
    def __init__(self, state: GameState | None = None, max_states: int = DEFAULT_MAX_UNDO_STATES) -> None:
        self.states = [state or GameState.initial()]
        self.max_states = max(1, max_states)
        self.cursor = 0
        self.created_at = _utc_now()
        self.updated_at = self.created_at

    @property
    def current(self) -> GameState:
        return self.states[self.cursor]

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def push(self, state: GameState) -> None:
        del self.states[self.cursor + 1 :]
        self.states.append(state)
        self._trim_states()
        self.cursor = len(self.states) - 1
        self.touch()

    def undo(self) -> GameState:
        if self.cursor > 0:
            self.cursor -= 1
        self.touch()
        return self.current

    def redo(self) -> GameState:
        if self.cursor < len(self.states) - 1:
            self.cursor += 1
        self.touch()
        return self.current

    def _trim_states(self) -> None:
        overflow = len(self.states) - self.max_states
        if overflow <= 0:
            return
        del self.states[:overflow]
        self.cursor = max(0, self.cursor - overflow)


class GameStore:
    def __init__(
        self,
        max_games: int = DEFAULT_MAX_GAME_SESSIONS,
        ttl_seconds: int = DEFAULT_GAME_TTL_SECONDS,
        max_states: int = DEFAULT_MAX_UNDO_STATES,
    ) -> None:
        self.games: dict[str, GameSession] = {}
        self.max_games = max(1, max_games)
        self.ttl = timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None
        self.max_states = max(1, max_states)
        self._lock = RLock()

    def create(self, state: GameState | None = None) -> tuple[str, GameState]:
        import uuid

        with self._lock:
            self._prune_locked()
            game_id = uuid.uuid4().hex
            self.games[game_id] = GameSession(state, max_states=self.max_states)
            self._prune_locked(exempt={game_id})
            return game_id, self.games[game_id].current

    def get(self, game_id: str) -> GameState | None:
        with self._lock:
            session = self._active_session(game_id)
            if session:
                session.touch()
            return session.current if session else None

    def snapshot(self, game_id: str) -> dict[str, object] | None:
        with self._lock:
            session = self._active_session(game_id)
            if not session:
                return None
            session.touch()
            return _game_session_snapshot(game_id, session)

    def push(self, game_id: str, state: GameState) -> GameState | None:
        with self._lock:
            session = self._active_session(game_id)
            if not session:
                return None
            session.push(state)
            self._prune_locked(exempt={game_id})
            return session.current

    def undo(self, game_id: str) -> GameState | None:
        with self._lock:
            session = self._active_session(game_id)
            if not session:
                return None
            return session.undo()

    def redo(self, game_id: str) -> GameState | None:
        with self._lock:
            session = self._active_session(game_id)
            if not session:
                return None
            return session.redo()

    def prune(self, exempt: set[str] | None = None) -> None:
        with self._lock:
            self._prune_locked(exempt)

    def _prune_locked(self, exempt: set[str] | None = None) -> None:
        exempt = exempt or set()
        now = _utc_now()
        if self.ttl is not None:
            expired = [
                game_id
                for game_id, session in self.games.items()
                if game_id not in exempt and now - session.updated_at > self.ttl
            ]
            for game_id in expired:
                self.games.pop(game_id, None)

        overflow = len(self.games) - self.max_games
        if overflow <= 0:
            return
        candidates = sorted(
            (
                (game_id, session)
                for game_id, session in self.games.items()
                if game_id not in exempt
            ),
            key=lambda item: item[1].updated_at,
        )
        for game_id, _session in candidates[:overflow]:
            self.games.pop(game_id, None)

    def _active_session(self, game_id: str) -> GameSession | None:
        session = self.games.get(game_id)
        if not session:
            return None
        if self.ttl is not None and _utc_now() - session.updated_at > self.ttl:
            self.games.pop(game_id, None)
            return None
        return session


def _game_session_snapshot(game_id: str, session: GameSession) -> dict[str, object]:
    return {
        "game_id": game_id,
        "state": session.current.to_dict(),
        "state_index": session.cursor,
        "state_history": [
            state.to_dict(include_legal_moves=index == session.cursor)
            for index, state in enumerate(session.states)
        ],
    }


def create_app(
    frontend_dir: Path | None = None,
    *,
    max_game_sessions: int = DEFAULT_MAX_GAME_SESSIONS,
    game_ttl_seconds: int = DEFAULT_GAME_TTL_SECONDS,
    max_undo_states: int = DEFAULT_MAX_UNDO_STATES,
    max_import_history: int = DEFAULT_MAX_IMPORT_HISTORY,
    max_online_rooms: int = 128,
    online_room_ttl_seconds: int = DEFAULT_GAME_TTL_SECONDS,
    max_ai_games: int = 128,
    ai_game_ttl_seconds: int = DEFAULT_GAME_TTL_SECONDS,
) -> FastAPI:
    app = FastAPI(title="Rolling Chess")
    game_store = GameStore(
        max_games=max_game_sessions,
        ttl_seconds=game_ttl_seconds,
        max_states=max_undo_states,
    )
    room_store = OnlineRoomStore(
        max_rooms=max_online_rooms,
        ttl_seconds=online_room_ttl_seconds,
    )
    ai_store = AIGameStore(
        max_games=max_ai_games,
        ttl_seconds=ai_game_ttl_seconds,
    )
    root = frontend_dir or _default_frontend_dir()

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/games")
    def create_game() -> dict[str, object]:
        game_id, state = game_store.create()
        return game_store.snapshot(game_id) or {"game_id": game_id, "state": state.to_dict()}

    @app.get("/api/games/{game_id}")
    def get_game(game_id: str) -> dict[str, object]:
        snapshot = game_store.snapshot(game_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="unknown game")
        return snapshot

    @app.post("/api/games/{game_id}/moves")
    def make_move(game_id: str, payload: dict[str, Any]) -> dict[str, object]:
        state = game_store.get(game_id)
        if state is None:
            raise HTTPException(status_code=404, detail="unknown game")
        try:
            move_text = _move_text_from_payload(payload)
            next_state = state.apply_move(move_text)
        except (RollingChessError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        stored_state = game_store.push(game_id, next_state)
        if stored_state is None:
            raise HTTPException(status_code=404, detail="unknown game")
        return game_store.snapshot(game_id) or {"game_id": game_id, "state": stored_state.to_dict()}

    @app.post("/api/games/{game_id}/undo")
    def undo(game_id: str) -> dict[str, object]:
        state = game_store.undo(game_id)
        if state is None:
            raise HTTPException(status_code=404, detail="unknown game")
        return game_store.snapshot(game_id) or {"game_id": game_id, "state": state.to_dict()}

    @app.post("/api/games/{game_id}/redo")
    def redo(game_id: str) -> dict[str, object]:
        state = game_store.redo(game_id)
        if state is None:
            raise HTTPException(status_code=404, detail="unknown game")
        return game_store.snapshot(game_id) or {"game_id": game_id, "state": state.to_dict()}

    @app.get("/api/games/{game_id}/export")
    def export_game(game_id: str) -> dict[str, object]:
        state = game_store.get(game_id)
        if state is None:
            raise HTTPException(status_code=404, detail="unknown game")
        return {"state": state.to_dict(include_legal_moves=False)}

    @app.post("/api/games/import")
    def import_game(payload: dict[str, Any]) -> dict[str, object]:
        try:
            state_payload = payload.get("state")
            if not isinstance(state_payload, dict):
                raise ValueError("import payload must include state")
            _validate_import_size(state_payload, max_import_history)
            state = GameState.from_dict(state_payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        game_id, state = game_store.create(state)
        return game_store.snapshot(game_id) or {"game_id": game_id, "state": state.to_dict()}

    @app.post("/api/rooms")
    def create_room(payload: dict[str, Any]) -> dict[str, object]:
        try:
            nickname = _nickname_from_payload(payload)
            room, player = room_store.create_room(nickname)
        except RoomError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "room_id": room.room_id,
            "player_token": player.token,
            "assigned_color": player.color.value,
            "room": room.snapshot(player.token),
        }

    @app.post("/api/rooms/{room_id}/join")
    def join_room(room_id: str, payload: dict[str, Any]) -> dict[str, object]:
        try:
            nickname = _nickname_from_payload(payload)
            token_value = payload.get("player_token")
            player_token = token_value if isinstance(token_value, str) and token_value else None
            room, player = room_store.join_room(room_id, nickname, player_token)
        except RoomError as exc:
            status = 404 if str(exc) == "room not found" else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        return {
            "room_id": room.room_id,
            "player_token": player.token,
            "assigned_color": player.color.value,
            "room": room.snapshot(player.token),
        }

    @app.get("/api/rooms/{room_id}")
    def get_room(room_id: str) -> dict[str, object]:
        try:
            room = room_store.get_room(room_id)
        except RoomError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"room": room.snapshot()}

    @app.post("/api/ai/games")
    def create_ai_game(payload: dict[str, Any]) -> dict[str, object]:
        try:
            player_color = payload.get("player_color", "white")
            difficulty = payload.get("difficulty", "normal")
            if not isinstance(player_color, str) or not isinstance(difficulty, str):
                raise AIGameError("player_color and difficulty must be strings")
            session = ai_store.create_game(player_color, difficulty)
        except (AIGameError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return session.snapshot()

    @app.get("/api/ai/games/{game_id}")
    def get_ai_game(game_id: str) -> dict[str, object]:
        try:
            return ai_store.get_game(game_id).snapshot()
        except AIGameError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/ai/games/{game_id}/moves")
    def make_ai_game_move(game_id: str, payload: dict[str, Any]) -> dict[str, object]:
        try:
            move_text = _move_text_from_payload(payload)
            result = ai_store.apply_player_move(game_id, move_text)
        except AIGameError as exc:
            status = 404 if str(exc) == "unknown AI game" else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        response = result.session.snapshot()
        response["player_state"] = result.player_state.to_dict()
        return response

    @app.post("/api/ai/games/{game_id}/player-moves")
    def make_ai_player_move(game_id: str, payload: dict[str, Any]) -> dict[str, object]:
        try:
            move_text = _move_text_from_payload(payload)
            session = ai_store.apply_player_move_only(game_id, move_text)
        except AIGameError as exc:
            status = 404 if str(exc) == "unknown AI game" else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return session.snapshot()

    @app.post("/api/ai/games/{game_id}/ai-move")
    def make_ai_reply_move(game_id: str) -> dict[str, object]:
        try:
            session = ai_store.apply_ai_move(game_id)
        except AIGameError as exc:
            status = 404 if str(exc) == "unknown AI game" else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        return session.snapshot()

    @app.websocket("/ws/rooms/{room_id}")
    async def room_socket(websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()
        token: str | None = None
        try:
            first_message = await websocket.receive_json()
            if first_message.get("type") != "join":
                await websocket.send_json({"type": "error", "error": "first message must be join"})
                await websocket.close(code=1008)
                return
            token_value = first_message.get("token")
            if not isinstance(token_value, str) or not token_value:
                await websocket.send_json({"type": "error", "error": "missing player token"})
                await websocket.close(code=1008)
                return
            token = token_value
            room = room_store.connect(room_id, token, websocket)
            await _broadcast_room_state(room)

            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message_type == "move":
                    await _handle_socket_move(room_store, room_id, token, message)
                elif message_type == "resign":
                    await _handle_socket_resign(room_store, room_id, token, message)
                elif message_type == "draw":
                    await _handle_socket_draw(room_store, room_id, token, message)
                elif message_type == "leave":
                    room = room_store.disconnect(room_id, token)
                    if room:
                        await _broadcast_room_state(room)
                    await websocket.close()
                    return
                else:
                    await websocket.send_json({"type": "error", "error": "unknown message type"})
        except WebSocketDisconnect:
            pass
        except RoomError as exc:
            await websocket.send_json({"type": "error", "error": str(exc)})
        finally:
            if token:
                room = room_store.disconnect(room_id, token)
                if room:
                    await _broadcast_room_state(room)

    @app.get("/{path:path}")
    def serve_static(path: str) -> Response:
        return _serve_static(root, path)

    app.state.game_store = game_store
    app.state.room_store = room_store
    app.state.ai_store = ai_store
    app.state.frontend_dir = root
    return app


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    frontend_dir: Path | None = None,
) -> FastAPI:
    # Kept as a compatibility alias for callers that previously imported create_server.
    return create_app(frontend_dir)


async def _handle_socket_move(
    room_store: OnlineRoomStore, room_id: str, token: str, message: dict[str, Any]
) -> None:
    move_value = message.get("move")
    version_value = message.get("version")
    connection = room_store.get_room(room_id).connections.get(token)
    if not isinstance(move_value, str) or not isinstance(version_value, int):
        if connection:
            await connection.send_json({"type": "move_rejected", "error": "move and version required"})
        return
    try:
        room = room_store.apply_move(room_id, token, move_value, version_value)
    except RoomError as exc:
        if connection:
            await connection.send_json({"type": "move_rejected", "error": str(exc)})
        return
    await _broadcast_room_state(room)


async def _handle_socket_resign(
    room_store: OnlineRoomStore, room_id: str, token: str, message: dict[str, Any]
) -> None:
    version_value = message.get("version")
    connection = room_store.get_room(room_id).connections.get(token)
    if not isinstance(version_value, int):
        if connection:
            await connection.send_json({"type": "move_rejected", "error": "version required"})
        return
    try:
        room = room_store.resign(room_id, token, version_value)
    except RoomError as exc:
        if connection:
            await connection.send_json({"type": "move_rejected", "error": str(exc)})
        return
    await _broadcast_room_state(room)


async def _handle_socket_draw(
    room_store: OnlineRoomStore, room_id: str, token: str, message: dict[str, Any]
) -> None:
    version_value = message.get("version")
    connection = room_store.get_room(room_id).connections.get(token)
    if not isinstance(version_value, int):
        if connection:
            await connection.send_json({"type": "move_rejected", "error": "version required"})
        return
    try:
        room = room_store.offer_or_accept_draw(room_id, token, version_value)
    except RoomError as exc:
        if connection:
            await connection.send_json({"type": "move_rejected", "error": str(exc)})
        return
    await _broadcast_room_state(room)


async def _broadcast_room_state(room: OnlineRoom) -> None:
    for token, connection in list(room.connections.items()):
        try:
            await connection.send_json({"type": "room_state", "room": room.snapshot(token)})
        except RuntimeError:
            room.connections.pop(token, None)


def _serve_static(frontend_dir: Path, path: str) -> Response:
    relative = "index.html" if path in {"", "/"} else path.lstrip("/")
    candidate = (frontend_dir / relative).resolve()
    try:
        candidate.relative_to(frontend_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="forbidden") from exc
    if not candidate.is_file():
        if "." not in Path(relative).name:
            candidate = frontend_dir / "index.html"
        else:
            raise HTTPException(status_code=404, detail="not found")
    content_type = mimetypes.guess_type(candidate.name)[0]
    if content_type:
        return FileResponse(candidate, media_type=content_type)
    return FileResponse(candidate)


def _default_frontend_dir() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    cwd_frontend = Path.cwd() / "frontend"
    if cwd_frontend.exists():
        return cwd_frontend
    return project_root / "frontend"


def _nickname_from_payload(payload: dict[str, Any]) -> str:
    nickname = payload.get("nickname")
    if not isinstance(nickname, str) or not nickname.strip():
        raise RoomError("nickname is required")
    return nickname


def _validate_import_size(state_payload: dict[str, object], max_history: int) -> None:
    history = state_payload.get("history", [])
    if isinstance(history, list) and len(history) > max_history:
        raise ValueError(f"import history may include at most {max_history} moves")
    history_details = state_payload.get("history_details")
    if isinstance(history_details, list) and len(history_details) > max_history:
        raise ValueError(f"import history_details may include at most {max_history} moves")


def _move_text_from_payload(payload: dict[str, object]) -> str:
    if isinstance(payload.get("move"), str):
        return str(payload["move"])
    source = payload.get("from")
    target = payload.get("to")
    promotion = payload.get("promotion", "")
    if not isinstance(source, str) or not isinstance(target, str):
        raise ValueError("move payload must include move or from/to")
    if promotion is None:
        promotion = ""
    if not isinstance(promotion, str):
        raise ValueError("promotion must be a string")
    return f"{source}{target}{promotion}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Rolling Chess web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
