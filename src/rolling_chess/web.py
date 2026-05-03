from __future__ import annotations

import argparse
import json
import mimetypes
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .exceptions import RollingChessError
from .state import GameState


@dataclass(slots=True)
class GameSession:
    states: list[GameState]
    cursor: int = 0

    @property
    def current(self) -> GameState:
        return self.states[self.cursor]

    def push(self, state: GameState) -> None:
        del self.states[self.cursor + 1 :]
        self.states.append(state)
        self.cursor = len(self.states) - 1

    def undo(self) -> GameState:
        if self.cursor > 0:
            self.cursor -= 1
        return self.current

    def redo(self) -> GameState:
        if self.cursor < len(self.states) - 1:
            self.cursor += 1
        return self.current


@dataclass(slots=True)
class GameStore:
    games: dict[str, GameSession] = field(default_factory=dict)

    def create(self, state: GameState | None = None) -> tuple[str, GameState]:
        game_id = uuid.uuid4().hex
        state = state or GameState.initial()
        self.games[game_id] = GameSession([state])
        return game_id, state

    def get(self, game_id: str) -> GameState | None:
        session = self.games.get(game_id)
        return session.current if session else None

    def push(self, game_id: str, state: GameState) -> None:
        self.games[game_id].push(state)

    def undo(self, game_id: str) -> GameState | None:
        session = self.games.get(game_id)
        if not session:
            return None
        return session.undo()

    def redo(self, game_id: str) -> GameState | None:
        session = self.games.get(game_id)
        if not session:
            return None
        return session.redo()


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    frontend_dir: Path | None = None,
) -> ThreadingHTTPServer:
    store = GameStore()
    root = frontend_dir or _default_frontend_dir()
    handler = _handler_factory(store, root)
    return ThreadingHTTPServer((host, port), handler)


def _default_frontend_dir() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    cwd_frontend = Path.cwd() / "frontend"
    if cwd_frontend.exists():
        return cwd_frontend
    return project_root / "frontend"


def _handler_factory(store: GameStore, frontend_dir: Path) -> type[BaseHTTPRequestHandler]:
    class RollingChessHandler(BaseHTTPRequestHandler):
        server_version = "RollingChessHTTP/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._send_json({"ok": True})
                return
            if parsed.path.startswith("/api/games/") and parsed.path.endswith("/export"):
                self._handle_export(parsed.path)
                return
            if parsed.path.startswith("/api/games/"):
                self._handle_get_game(parsed.path)
                return
            self._serve_static(parsed.path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/games":
                game_id, state = store.create()
                self._send_json({"game_id": game_id, "state": state.to_dict()})
                return
            if parsed.path == "/api/games/import":
                self._handle_import()
                return
            if parsed.path.startswith("/api/games/") and parsed.path.endswith("/moves"):
                self._handle_move(parsed.path)
                return
            if parsed.path.startswith("/api/games/") and parsed.path.endswith("/undo"):
                self._handle_undo(parsed.path)
                return
            if parsed.path.startswith("/api/games/") and parsed.path.endswith("/redo"):
                self._handle_redo(parsed.path)
                return
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _handle_get_game(self, path: str) -> None:
            game_id = _path_part(path, 2)
            state = store.get(game_id)
            if state is None:
                self._send_json({"error": "unknown game"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"game_id": game_id, "state": state.to_dict()})

        def _handle_move(self, path: str) -> None:
            game_id = _path_part(path, 2)
            state = store.get(game_id)
            if state is None:
                self._send_json({"error": "unknown game"}, HTTPStatus.NOT_FOUND)
                return
            try:
                payload = self._read_json()
                move_text = _move_text_from_payload(payload)
                next_state = state.apply_move(move_text)
            except RollingChessError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            store.push(game_id, next_state)
            self._send_json({"game_id": game_id, "state": next_state.to_dict()})

        def _handle_undo(self, path: str) -> None:
            game_id = _path_part(path, 2)
            state = store.undo(game_id)
            if state is None:
                self._send_json({"error": "unknown game"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"game_id": game_id, "state": state.to_dict()})

        def _handle_redo(self, path: str) -> None:
            game_id = _path_part(path, 2)
            state = store.redo(game_id)
            if state is None:
                self._send_json({"error": "unknown game"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"game_id": game_id, "state": state.to_dict()})

        def _handle_export(self, path: str) -> None:
            game_id = _path_part(path, 2)
            state = store.get(game_id)
            if state is None:
                self._send_json({"error": "unknown game"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"state": state.to_dict(include_legal_moves=False)})

        def _handle_import(self) -> None:
            try:
                payload = self._read_json()
                state_payload = payload.get("state")
                if not isinstance(state_payload, dict):
                    raise ValueError("import payload must include state")
                state = GameState.from_dict(state_payload)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            game_id, state = store.create(state)
            self._send_json({"game_id": game_id, "state": state.to_dict()})

        def _read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("invalid JSON body") from exc
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            return payload

        def _send_json(
            self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK
        ) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, path: str) -> None:
            relative = "index.html" if path == "/" else unquote(path).lstrip("/")
            candidate = (frontend_dir / relative).resolve()
            try:
                candidate.relative_to(frontend_dir.resolve())
            except ValueError:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not candidate.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            body = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return RollingChessHandler


def _path_part(path: str, index: int) -> str:
    parts = [part for part in path.split("/") if part]
    return parts[index]


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

    server = create_server(args.host, args.port)
    host, port = server.server_address
    print(f"Rolling Chess server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
