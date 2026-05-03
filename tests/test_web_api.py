from __future__ import annotations

import http.client
import json
import threading

import pytest

from rolling_chess.web import create_server


@pytest.fixture
def web_server():
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(server, method: str, path: str, payload: dict[str, object] | None = None):
    host, port = server.server_address
    connection = http.client.HTTPConnection(host, port, timeout=5)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    content_type = response.getheader("Content-Type", "")
    if "application/json" in content_type:
        data = json.loads(raw.decode("utf-8"))
    else:
        data = raw.decode("utf-8")
    connection.close()
    return response.status, data


def test_web_api_game_lifecycle(web_server):
    status, created = request(web_server, "POST", "/api/games")
    assert status == 200
    game_id = created["game_id"]
    assert created["state"]["turn"] == "white"

    status, moved = request(web_server, "POST", f"/api/games/{game_id}/moves", {"move": "e2e4"})
    assert status == 200
    assert moved["state"]["turn"] == "black"
    assert moved["state"]["history"] == ["e2e4"]
    assert moved["state"]["history_details"][-1]["capture"] is None

    status, rejected = request(web_server, "POST", f"/api/games/{game_id}/moves", {"move": "e2e5"})
    assert status == 400
    assert "error" in rejected

    status, undone = request(web_server, "POST", f"/api/games/{game_id}/undo")
    assert status == 200
    assert undone["state"]["turn"] == "white"
    assert undone["state"]["history"] == []

    status, redone = request(web_server, "POST", f"/api/games/{game_id}/redo")
    assert status == 200
    assert redone["state"]["turn"] == "black"
    assert redone["state"]["history"] == ["e2e4"]


def test_web_api_history_details_show_capture(web_server):
    status, created = request(web_server, "POST", "/api/games")
    assert status == 200
    game_id = created["game_id"]

    for move in ("e2e4", "d7d5", "e4d5"):
        status, payload = request(web_server, "POST", f"/api/games/{game_id}/moves", {"move": move})
        assert status == 200

    detail = payload["state"]["history_details"][-1]
    assert detail["move"] == "e4d5"
    assert detail["from"] == "e4"
    assert detail["to"] == "d5"
    assert detail["capture"] == "p"
    assert detail["capture_symbol"] == "p"
    assert detail["capture_kind"] == "normal"


def test_web_api_export_import(web_server):
    status, created = request(web_server, "POST", "/api/games")
    assert status == 200
    game_id = created["game_id"]
    status, moved = request(web_server, "POST", f"/api/games/{game_id}/moves", {"move": "e2e4"})
    assert status == 200

    status, exported = request(web_server, "GET", f"/api/games/{game_id}/export")
    assert status == 200
    assert exported["state"]["history"] == ["e2e4"]
    assert exported["state"]["history_details"][0]["move"] == "e2e4"
    assert "legal_moves" not in exported["state"]

    status, imported = request(web_server, "POST", "/api/games/import", exported)
    assert status == 200
    assert imported["game_id"] != game_id
    assert imported["state"]["history"] == moved["state"]["history"]
    assert imported["state"]["history_details"] == moved["state"]["history_details"]
    assert imported["state"]["turn"] == moved["state"]["turn"]


def test_web_server_serves_frontend(web_server):
    status, html = request(web_server, "GET", "/")
    assert status == 200
    assert "Rolling Chess" in html
    assert "white-captured" in html
    assert "black-captured" in html
    assert "left-file" in html

    status, js = request(web_server, "GET", "/src/main.js")
    assert status == 200
    assert "newGame" in js
    assert "saveGame" in js
    assert "capturedPiecesFromBoard" in js
    assert "formatHistoryEntry" in js
    assert "leftFileIndex" in js
