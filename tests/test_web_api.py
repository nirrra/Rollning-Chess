from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rolling_chess import GameState
from rolling_chess.online import OnlineRoomStore, RoomError
from rolling_chess.web import GameStore, create_app


def request(
    client: TestClient, method: str, path: str, payload: dict[str, object] | None = None
):
    response = client.request(method, path, json=payload)
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        data = response.json()
    else:
        data = response.text
    return response.status_code, data


def test_web_api_game_lifecycle():
    client = TestClient(create_app())
    status, created = request(client, "POST", "/api/games")
    assert status == 200
    game_id = created["game_id"]
    assert created["state"]["turn"] == "white"

    status, moved = request(client, "POST", f"/api/games/{game_id}/moves", {"move": "e2e4"})
    assert status == 200
    assert moved["state"]["turn"] == "black"
    assert moved["state"]["history"] == ["e2e4"]
    first_detail = moved["state"]["history_details"][-1]
    assert first_detail["piece"] == "p"
    assert first_detail["piece_symbol"] == "P"
    assert first_detail["capture"] is None

    status, rejected = request(client, "POST", f"/api/games/{game_id}/moves", {"move": "e2e5"})
    assert status == 400
    assert "detail" in rejected

    status, undone = request(client, "POST", f"/api/games/{game_id}/undo")
    assert status == 200
    assert undone["state"]["turn"] == "white"
    assert undone["state"]["history"] == []

    status, redone = request(client, "POST", f"/api/games/{game_id}/redo")
    assert status == 200
    assert redone["state"]["turn"] == "black"
    assert redone["state"]["history"] == ["e2e4"]


def test_game_store_prunes_sessions_and_caps_undo_history():
    store = GameStore(max_games=1, ttl_seconds=0, max_states=2)
    first_id, _state = store.create()
    second_id, state = store.create()

    assert store.get(first_id) is None
    assert store.get(second_id) is not None

    for move in ("e2e4", "e7e5", "g1f3"):
        next_state = state.apply_move(move)
        state = store.push(second_id, next_state)
        assert state is not None

    assert len(store.games[second_id].states) == 2
    undone = store.undo(second_id)
    assert undone is not None
    assert undone.history == ("e2e4", "e7e5")
    oldest = store.undo(second_id)
    assert oldest is not None
    assert oldest.history == ("e2e4", "e7e5")


def test_import_rejects_oversized_history_before_building_state():
    client = TestClient(create_app(max_import_history=1))
    state_payload = GameState.initial().to_dict(include_legal_moves=False)
    state_payload["history"] = ["e2e4", "e7e5"]

    status, rejected = request(client, "POST", "/api/games/import", {"state": state_payload})

    assert status == 400
    assert "at most 1 moves" in rejected["detail"]


def test_web_api_history_details_show_capture():
    client = TestClient(create_app())
    status, created = request(client, "POST", "/api/games")
    assert status == 200
    game_id = created["game_id"]

    for move in ("e2e4", "d7d5", "e4d5"):
        status, payload = request(client, "POST", f"/api/games/{game_id}/moves", {"move": move})
        assert status == 200

    detail = payload["state"]["history_details"][-1]
    assert detail["move"] == "e4d5"
    assert detail["from"] == "e4"
    assert detail["to"] == "d5"
    assert detail["piece"] == "p"
    assert detail["piece_symbol"] == "P"
    assert detail["capture"] == "p"
    assert detail["capture_symbol"] == "p"
    assert detail["capture_kind"] == "normal"


def test_web_api_export_import():
    client = TestClient(create_app())
    status, created = request(client, "POST", "/api/games")
    assert status == 200
    game_id = created["game_id"]
    status, moved = request(client, "POST", f"/api/games/{game_id}/moves", {"move": "e2e4"})
    assert status == 200

    status, exported = request(client, "GET", f"/api/games/{game_id}/export")
    assert status == 200
    assert exported["state"]["history"] == ["e2e4"]
    assert exported["state"]["history_details"][0]["move"] == "e2e4"
    assert "legal_moves" not in exported["state"]

    status, imported = request(client, "POST", "/api/games/import", exported)
    assert status == 200
    assert imported["game_id"] != game_id
    assert imported["state"]["history"] == moved["state"]["history"]
    assert imported["state"]["history_details"] == moved["state"]["history_details"]
    assert imported["state"]["turn"] == moved["state"]["turn"]


def test_online_room_store_prunes_inactive_lru_rooms():
    store = OnlineRoomStore(max_rooms=1, ttl_seconds=0)
    first_room, _first_player = store.create_room("Atlas")
    second_room, _second_player = store.create_room("Nocturne")

    with pytest.raises(RoomError, match="room not found"):
        store.get_room(first_room.room_id)
    assert store.get_room(second_room.room_id).room_id == second_room.room_id


def test_online_room_resign_finishes_room():
    store = OnlineRoomStore()
    room, first_player = store.create_room("Atlas")
    room, _second_player = store.join_room(room.room_id, "Nocturne")

    resigned = store.resign(room.room_id, first_player.token, room.version)

    assert resigned.status.value == "finished"
    snapshot = resigned.snapshot(first_player.token)
    assert snapshot["outcome"] == {
        "reason": "resignation",
        "winner": first_player.color.other().value,
    }


def test_online_room_draw_requires_both_players():
    store = OnlineRoomStore()
    room, first_player = store.create_room("Atlas")
    room, second_player = store.join_room(room.room_id, "Nocturne")

    offered = store.offer_or_accept_draw(room.room_id, first_player.token, room.version)

    assert offered.status.value == "active"
    assert offered.draw_offer_by == first_player.color
    assert offered.snapshot(second_player.token)["draw_offer_by"] == first_player.color.value

    accepted = store.offer_or_accept_draw(room.room_id, second_player.token, offered.version)

    assert accepted.status.value == "finished"
    assert accepted.snapshot(second_player.token)["outcome"] == {
        "reason": "draw",
        "winner": None,
    }


def test_ai_game_api_white_player_move_gets_ai_reply():
    client = TestClient(create_app())
    status, created = request(
        client,
        "POST",
        "/api/ai/games",
        {"player_color": "white", "difficulty": "easy"},
    )
    assert status == 200
    assert created["player_color"] == "white"
    assert created["ai_color"] == "black"
    assert created["state"]["history"] == []
    assert created["last_ai_move"] is None

    status, moved = request(
        client,
        "POST",
        f"/api/ai/games/{created['game_id']}/moves",
        {"move": "e2e4"},
    )
    assert status == 200
    assert moved["state"]["turn"] == "white"
    assert len(moved["state"]["history"]) == 2
    assert moved["state"]["history"][0] == "e2e4"
    assert moved["player_state"]["turn"] == "black"
    assert moved["player_state"]["history"] == ["e2e4"]
    assert moved["last_ai_move"] == moved["state"]["history"][1]


def test_ai_game_api_can_apply_player_then_ai_as_separate_steps():
    client = TestClient(create_app())
    status, created = request(
        client,
        "POST",
        "/api/ai/games",
        {"player_color": "white", "difficulty": "easy"},
    )
    assert status == 200

    status, player_moved = request(
        client,
        "POST",
        f"/api/ai/games/{created['game_id']}/player-moves",
        {"move": "e2e4"},
    )
    assert status == 200
    assert player_moved["state"]["history"] == ["e2e4"]
    assert player_moved["state"]["turn"] == "black"
    assert player_moved["last_ai_move"] is None

    status, ai_moved = request(
        client,
        "POST",
        f"/api/ai/games/{created['game_id']}/ai-move",
    )
    assert status == 200
    assert ai_moved["state"]["turn"] == "white"
    assert len(ai_moved["state"]["history"]) == 2
    assert ai_moved["last_ai_move"] == ai_moved["state"]["history"][1]


def test_ai_game_api_black_player_gets_opening_ai_move():
    client = TestClient(create_app())
    status, created = request(
        client,
        "POST",
        "/api/ai/games",
        {"player_color": "black", "difficulty": "easy"},
    )
    assert status == 200
    assert created["player_color"] == "black"
    assert created["ai_color"] == "white"
    assert created["state"]["turn"] == "black"
    assert len(created["state"]["history"]) == 1
    assert created["last_ai_move"] == created["state"]["history"][0]


def test_ai_game_api_rejects_invalid_requests():
    client = TestClient(create_app())
    status, rejected = request(
        client,
        "POST",
        "/api/ai/games",
        {"player_color": "white", "difficulty": "impossible"},
    )
    assert status == 400
    assert "invalid difficulty" in rejected["detail"]

    status, created = request(
        client,
        "POST",
        "/api/ai/games",
        {"player_color": "white", "difficulty": "easy"},
    )
    assert status == 200
    status, rejected = request(
        client,
        "POST",
        f"/api/ai/games/{created['game_id']}/moves",
        {"move": "e2e5"},
    )
    assert status == 400
    assert "illegal move" in rejected["detail"]


def test_web_server_serves_frontend():
    client = TestClient(create_app())
    status, html = request(client, "GET", "/")
    assert status == 200
    assert "Rolling Chess" in html
    assert "nickname" in html
    assert "create-room" in html
    assert "start-ai-game" in html
    assert "ai-player-color" in html
    assert "ai-difficulty" in html
    assert "join-room-form" in html
    assert "game-app" in html
    assert "home-button" in html
    assert "white-captured" in html
    assert "black-captured" in html
    assert "left-file" in html
    assert "board-view-toggle" in html
    assert "View: 15x8" in html

    status, html = request(client, "GET", "/game/local")
    assert status == 200
    assert "Rolling Chess" in html

    status, js = request(client, "GET", "/src/main.js")
    assert status == 200
    assert "newGame" in js
    assert "saveGame" in js
    assert "capturedPiecesFromBoard" in js
    assert "formatHistoryEntry" in js
    assert "movingPieceSymbol" in js
    assert "latestMoveEntry" in js
    assert "last-move-to" in js
    assert "leftFileIndex" in js
    assert "handleSquarePointerDown" in js
    assert "pointermove" in js
    assert "visibleFileCount" in js
    assert "visibleRanks" in js
    assert "isBoardFlipped" in js
    assert "board-flipped" in js
    assert "boardView" in js
    assert "View: 8x8" in js
    assert "displaySquare" in js
    assert "displayMove" in js
    assert "handleContextMenu" in js
    assert "cancelDragInteraction" in js
    assert "startAIGame" in js
    assert "clockStarted" in js
    assert "player-moves" in js
    assert "ai-move" in js
    assert "/api/ai/games" in js
    assert "/game/ai/" in js
    assert "reviewMoveNumber" in js
    assert "state_history" in js
    assert "resignOnlineGame" in js
    assert "offerOrAcceptDraw" in js


def test_online_room_create_join_rejoin_and_full_room():
    client = TestClient(create_app())
    status, created = request(client, "POST", "/api/rooms", {"nickname": "Atlas"})
    assert status == 200
    room_id = created["room_id"]
    first_color = created["assigned_color"]
    assert first_color in {"white", "black"}
    assert created["player_token"]
    assert created["room"]["viewer_color"] == first_color

    status, joined = request(client, "POST", f"/api/rooms/{room_id}/join", {"nickname": "Nocturne"})
    assert status == 200
    assert joined["assigned_color"] in {"white", "black"}
    assert joined["assigned_color"] != first_color
    assert joined["player_token"] != created["player_token"]

    status, rejoined = request(
        client,
        "POST",
        f"/api/rooms/{room_id}/join",
        {"nickname": "Atlas Prime", "player_token": created["player_token"]},
    )
    assert status == 200
    assert rejoined["player_token"] == created["player_token"]
    assert rejoined["assigned_color"] == first_color

    status, rejected = request(client, "POST", f"/api/rooms/{room_id}/join", {"nickname": "Third"})
    assert status == 400
    assert rejected["detail"] == "room is full"

    status, public_room = request(client, "GET", f"/api/rooms/{room_id}")
    assert status == 200
    public_text = str(public_room)
    assert created["player_token"] not in public_text
    assert joined["player_token"] not in public_text


def test_online_room_websocket_move_sync_and_rejections():
    client = TestClient(create_app())
    _, created = request(client, "POST", "/api/rooms", {"nickname": "Atlas"})
    room_id = created["room_id"]
    _, joined = request(client, "POST", f"/api/rooms/{room_id}/join", {"nickname": "Nocturne"})

    seats = {
        created["assigned_color"]: created["player_token"],
        joined["assigned_color"]: joined["player_token"],
    }
    with client.websocket_connect(f"/ws/rooms/{room_id}") as white_ws:
        white_ws.send_json({"type": "join", "room_id": room_id, "token": seats["white"]})
        first_state = white_ws.receive_json()
        assert first_state["type"] == "room_state"
        with client.websocket_connect(f"/ws/rooms/{room_id}") as black_ws:
            black_ws.send_json({"type": "join", "room_id": room_id, "token": seats["black"]})
            white_ws.receive_json()
            black_ws.receive_json()

            white_ws.send_json({"type": "move", "move": "e2e4", "version": 0})
            white_update = white_ws.receive_json()
            black_update = black_ws.receive_json()
            assert white_update["type"] == "room_state"
            assert black_update["type"] == "room_state"
            assert white_update["room"]["state"]["turn"] == "black"
            assert black_update["room"]["state"]["history"] == ["e2e4"]
            assert len(black_update["room"]["state_history"]) == 2
            assert white_update["room"]["version"] == 1

            white_ws.send_json({"type": "move", "move": "d2d4", "version": 1})
            rejected = white_ws.receive_json()
            assert rejected["type"] == "move_rejected"
            assert rejected["error"] == "not your turn"
