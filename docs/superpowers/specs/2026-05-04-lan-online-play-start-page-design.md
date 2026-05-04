# LAN Online Play and Start Page Design

## Purpose

Rolling Chess currently supports a local rules engine and browser UI for single-device play. The next step is LAN-based two-player online play without requiring a cloud server. One computer acts as the host and server; other players on the same local network join through the host machine's address.

The first online version focuses on reliable direct play over a local network. It does not include public accounts, matchmaking, cloud hosting, spectators, chat, ratings, or forced timeout loss.

## Confirmed Product Decisions

- Hosting model: one computer runs the server with `rolling-chess-web --host 0.0.0.0 --port 8000`.
- Network scope: LAN only.
- Color assignment: random when the room is created.
- Room capacity: exactly two players; spectators are not supported.
- Reconnection: the same browser can refresh and return to the same seat using a saved player token.
- Online controls: online rooms disable local `Undo`, `Redo`, `Save`, and `Load`.
- Timers: clocks may display and synchronize, but timeout does not decide the game in the first version.
- Realtime transport: WebSocket.
- Server stack: migrate the web layer to FastAPI + Uvicorn.
- Room entry: support both full room links and room-code entry.
- Player identity: players enter a nickname; avatar is generated from the nickname initial.

## Page Structure

### Start Page: `/`

The start page is a functional lobby, not a marketing page. It should keep the current parchment/atlas visual direction while making the entry choices clear.

It contains:

- Nickname input, persisted in `localStorage`.
- `Local Game` action, routing to `/game/local`.
- `Create LAN Room` action, creating a room and then routing to `/room/{room_id}`.
- `Join Room` form, accepting a room code and routing to `/room/{room_id}`.
- After creating a room, display the room code and a full LAN link that can be copied.
- A concise host instruction: start the server with `--host 0.0.0.0` and share `http://host-ip:8000`.

The page may show the server-reported LAN address if the backend can discover it safely. If automatic discovery is unreliable, the UI should show clear manual instructions instead of guessing.

### Local Game: `/game/local`

Local mode preserves the current single-browser experience:

- Existing chessboard UI.
- Click-to-move and drag-to-move.
- 8x8 and 15x8 display modes.
- File rotation control.
- Captured pieces in player strips.
- Move history.
- `New`, `Undo`, `Redo`, `Save`, and `Load`.

Local mode can keep default names such as `Atlas` and `Nocturne` unless the lobby nickname is already available.

### Online Room: `/room/{room_id}`

Online mode reuses the chessboard UI but changes behavior and controls:

- Player strips show nickname, generated avatar, assigned color, connection state, and clock.
- The current browser's player strip is marked with `You`.
- If only one player is present, the room shows `Waiting for opponent`.
- Only the player whose color matches `state.turn` can move.
- Non-turn players cannot select or drag pieces.
- Right-side controls become `Copy Link`, `Leave`, and `New Local`.
- `Undo`, `Redo`, `Save`, and `Load` are hidden or disabled in online rooms.
- If the room does not exist or is full, the UI returns to the start page with an error message.

## Backend Architecture

The current `http.server` layer should be replaced by FastAPI + Uvicorn. The rules engine remains separate and authoritative. Online room logic should not be embedded inside `GameState`.

Suggested modules:

- `rolling_chess.web`: FastAPI app factory and server entrypoint.
- `rolling_chess.online`: room store, player model, room model, WebSocket broadcast logic.
- Existing rules modules remain unchanged unless a small serialization helper is required.

The CLI command `rolling-chess-web` remains the entrypoint. It should accept `--host` and `--port`. The default may remain `127.0.0.1` for local-only safety, with documentation explaining that LAN play needs `--host 0.0.0.0`.

## Online Room Model

`OnlineRoom`:

- `room_id: str`
- `state: GameState`
- `players: dict[Color, OnlinePlayer]`
- `created_at: datetime`
- `updated_at: datetime`
- `version: int`
- `status: waiting | active | finished`
- `connections: dict[str, WebSocket]`

`OnlinePlayer`:

- `token: str`
- `nickname: str`
- `color: white | black`
- `connected: bool`
- `last_seen: datetime`

The room store is in memory for the first version. Restarting the host process clears rooms.

## HTTP API

Existing local game endpoints should continue to work for local mode. New online endpoints:

`POST /api/rooms`

Request:

```json
{ "nickname": "Atlas" }
```

Response:

```json
{
  "room_id": "ABC123",
  "player_token": "opaque-token",
  "assigned_color": "white",
  "room": {}
}
```

Behavior:

- Create a room.
- Randomly assign the creator white or black.
- Generate an opaque token.
- Return the initial room state.

`POST /api/rooms/{room_id}/join`

Request:

```json
{ "nickname": "Nocturne", "player_token": "optional-existing-token" }
```

Behavior:

- If token matches an existing player, restore that seat.
- If token is absent and one seat is free, assign the remaining color.
- If room is full and token does not match, reject the request.

`GET /api/rooms/{room_id}`

Returns public room metadata and current state for initialization and error handling. It must not expose other players' tokens.

## WebSocket Protocol

Endpoint:

`WS /ws/rooms/{room_id}`

Client messages:

`join`

```json
{
  "type": "join",
  "room_id": "ABC123",
  "token": "opaque-token",
  "nickname": "Atlas"
}
```

`move`

```json
{
  "type": "move",
  "move": "e2e4",
  "version": 3
}
```

`leave`

```json
{ "type": "leave" }
```

`ping`

```json
{ "type": "ping" }
```

Server messages:

- `room_state`: complete room snapshot for rendering.
- `move_rejected`: move failed because it was illegal, out of turn, wrong color, or stale version.
- `player_connected`: another player connected.
- `player_disconnected`: another player disconnected.
- `error`: unrecoverable room or identity error.

The server is authoritative. Online clients do not commit final move state locally; they submit a move and render the next `room_state` broadcast.

## Move Validation

For every online move, the server checks:

- The room exists.
- The token belongs to a player in the room.
- The player's color equals `GameState.turn`.
- The move's source square contains the player's own piece.
- The client version matches the room version.
- `GameState.apply_move(move)` accepts the move.

If accepted:

- Update `room.state`.
- Increment `room.version`.
- Update `updated_at`.
- Broadcast `room_state` to both players.

If rejected:

- Send `move_rejected` to the sender only.
- Keep the room state unchanged.

## Frontend Architecture

The current frontend should be split so local and online behavior remain understandable.

Suggested files:

- `app.js`: route detection and page initialization.
- `lobby.js`: nickname, create room, join room, copy link.
- `board.js`: board rendering, 8x8/15x8 display, file rotation, click and drag move attempts.
- `local-game.js`: current local game behavior and local controls.
- `online-game.js`: room join, WebSocket connection, reconnect, online move submission.
- `ui-state.js`: player strips, active marker, clocks, captured pieces, history, error messages.

The board module should expose callbacks rather than know whether it is in local or online mode. For example, `onMoveAttempt(move)` can call either the local REST move endpoint or the online WebSocket sender.

## Reconnection

On room creation or join, the frontend stores:

```text
rolling-chess-room-{room_id} = { token, nickname, color }
```

When `/room/{room_id}` loads:

- If a saved token exists, attempt to reconnect with it.
- If no token exists, show the join flow for that room.
- If the token is accepted, restore the original color and player identity.
- If the room is full and the token is not recognized, show `Room is full`.

Disconnect behavior:

- Keep the last known board visible.
- Mark disconnected players in the player strips.
- Show `Reconnecting` for the current browser if its socket drops.
- Retry with bounded backoff.

## Timers

The first online version may synchronize clock display, but timeout does not decide the result. The server can include timer fields in `room_state` so both clients render the same values, but the rules engine should not treat clock expiration as game-ending.

This keeps the online rules focused on move legality and avoids disputes caused by LAN pauses, sleeps, or browser throttling.

## Error Handling

The UI should handle:

- Room not found.
- Room full.
- Nickname missing.
- WebSocket disconnected.
- Reconnect failed.
- Illegal move.
- Stale room version.
- Opponent disconnected.

Errors should be shown in the existing status area or a lobby-level notice. They should not use browser alerts.

## Testing Plan

### Stage 1: FastAPI Migration

Implement FastAPI static serving and preserve existing REST APIs.

Tests:

- Existing web API lifecycle tests still pass.
- Static `/`, `/src/main.js`, and `/src/styles.css` return expected content.
- Import/export remains compatible.

### Stage 2: Start Page and Local Route

Add `/` lobby and `/game/local` game route while preserving local play.

Tests:

- Lobby renders nickname input and local/online actions.
- Local game route renders the board.
- Click-to-move and drag-to-move still work.
- 8x8 and 15x8 display still work.

### Stage 3: Online Room HTTP API

Add create/join/read room endpoints.

Tests:

- Creating a room returns room id, token, and assigned color.
- Second player receives the remaining color.
- Third player is rejected.
- Existing token restores the same seat.
- Tokens are not leaked through public room data.

### Stage 4: WebSocket Online Play

Add room WebSocket endpoint and authoritative move flow.

Tests:

- Two clients connect to one room.
- A legal white move updates both clients.
- A non-turn move is rejected.
- A move from the wrong color is rejected.
- A stale version move is rejected.
- Refresh/reconnect with token restores the seat.

### Stage 5: LAN Browser Verification

Verify the real user flow in browser contexts.

Tests:

- Host starts `rolling-chess-web --host 0.0.0.0 --port 8000`.
- Player A creates a room.
- Player B joins with code or link.
- Both see assigned colors and nicknames.
- Moves synchronize through WebSocket.
- Captures, history, active player marker, and board view mode update correctly.
- Same-browser refresh restores the player's seat.

## Acceptance Criteria

- A host can run one server process and share a LAN URL.
- Two players on the same LAN can join the same room using a link or room code.
- The room randomly assigns white and black.
- Each player can only move on their own turn.
- The server rejects illegal, stale, or unauthorized moves.
- Both clients stay synchronized after every legal move.
- Refreshing the same browser restores the original seat.
- Online mode has room-specific controls; local-only controls are not available online.
- Existing local mode remains functional.
