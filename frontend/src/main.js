const lobbyEl = document.querySelector("#lobby");
const gameAppEl = document.querySelector("#game-app");
const nicknameInput = document.querySelector("#nickname");
const localGameButton = document.querySelector("#local-game");
const createRoomButton = document.querySelector("#create-room");
const startAIButton = document.querySelector("#start-ai-game");
const aiPlayerColorSelect = document.querySelector("#ai-player-color");
const aiDifficultySelect = document.querySelector("#ai-difficulty");
const joinRoomForm = document.querySelector("#join-room-form");
const roomCodeInput = document.querySelector("#room-code");
const lobbyResultEl = document.querySelector("#lobby-result");
const homeButton = document.querySelector("#home-button");
const boardEl = document.querySelector("#board");
const filesTopEl = document.querySelector("#files-top");
const filesBottomEl = document.querySelector("#files-bottom");
const rankLabelEls = document.querySelectorAll(".ranks");
const leftFileInput = document.querySelector("#left-file");
const leftFileLabel = document.querySelector("#left-file-label");
const rotatePrevButton = document.querySelector("#rotate-prev");
const rotateNextButton = document.querySelector("#rotate-next");
const boardViewToggle = document.querySelector("#board-view-toggle");
const statusEl = document.querySelector("#status");
const historyEl = document.querySelector("#history");
const newGameButton = document.querySelector("#new-game");
const undoButton = document.querySelector("#undo");
const redoButton = document.querySelector("#redo");
const saveButton = document.querySelector("#save");
const loadButton = document.querySelector("#load");
const whiteCapturedEl = document.querySelector("#white-captured");
const blackCapturedEl = document.querySelector("#black-captured");
const whitePlayerEl = document.querySelector("#white-player");
const blackPlayerEl = document.querySelector("#black-player");
const whiteClockEl = document.querySelector("#white-clock");
const blackClockEl = document.querySelector("#black-clock");
const promotionEl = document.querySelector("#promotion");
const storageKey = "rolling-chess-save";
const nicknameStorageKey = "rolling-chess-nickname";

const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
const pieceOrder = ["q", "r", "b", "n", "p"];
const initialMaterial = {
  white: { k: 1, q: 1, r: 2, b: 2, n: 2, p: 8 },
  black: { k: 1, q: 1, r: 2, b: 2, n: 2, p: 8 },
};
const pieceSymbols = {
  K: "♔",
  Q: "♕",
  R: "♖",
  B: "♗",
  N: "♘",
  P: "♙",
  k: "♚",
  q: "♛",
  r: "♜",
  b: "♝",
  n: "♞",
  p: "♟",
};

let gameId = null;
let state = null;
let selected = null;
let pendingPromotion = null;
let leftFileIndex = 0;
let boardView = "standard";
let dragState = null;
let suppressNextClick = false;
let clocks = { white: 600, black: 600 };
let clockStarted = false;
let lastClockTick = Date.now();
let appMode = "lobby";
let currentRoomId = null;
let playerToken = null;
let playerColor = null;
let roomVersion = 0;
let roomData = null;
let roomSocket = null;
let reconnectTimer = null;
let aiGameId = null;
let aiColor = null;
let aiDifficulty = "normal";
let aiLastMove = null;
let aiModelStatus = "not_used";
let aiThinking = false;

const dragThreshold = 6;
const initialClockSeconds = 10 * 60;

function squareName(file, rank) {
  return `${files[file]}${rank}`;
}

function displayFile(file) {
  return file.toUpperCase();
}

function displaySquare(square) {
  if (!square) {
    return square;
  }
  return `${square[0].toUpperCase()}${square.slice(1)}`;
}

function displayMove(move) {
  if (typeof move !== "string" || move.length < 4) {
    return move;
  }
  return `${displaySquare(move.slice(0, 2))}${displaySquare(move.slice(2, 4))}${move.slice(4).toUpperCase()}`;
}

function displayFileAt(position) {
  return (leftFileIndex + position) % 8;
}

function visibleFileCount() {
  return boardView === "wide" ? 15 : 8;
}

function rotatedFiles() {
  return Array.from({ length: visibleFileCount() }, (_, index) => files[displayFileAt(index)]);
}

function isBoardFlipped() {
  return (appMode === "online" || appMode === "ai") && playerColor === "black";
}

function visibleRanks() {
  return isBoardFlipped() ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
}

function fileIndex(square) {
  return files.indexOf(square[0]);
}

function roomStorageKey(roomId) {
  return `rolling-chess-room-${roomId}`;
}

function currentNickname() {
  const nickname = nicknameInput.value.trim() || "Atlas";
  localStorage.setItem(nicknameStorageKey, nickname);
  return nickname;
}

function displayNickname() {
  return nicknameInput.value.trim() || localStorage.getItem(nicknameStorageKey) || "Atlas";
}

function savedRoomIdentity(roomId) {
  const saved = localStorage.getItem(roomStorageKey(roomId));
  if (!saved) {
    return null;
  }
  try {
    return JSON.parse(saved);
  } catch {
    return null;
  }
}

function saveRoomIdentity(roomId, identity) {
  localStorage.setItem(roomStorageKey(roomId), JSON.stringify(identity));
}

function roomIdFromPath() {
  const match = window.location.pathname.match(/^\/room\/([^/]+)$/i);
  return match ? match[1].toUpperCase() : null;
}

function aiGameIdFromPath() {
  const match = window.location.pathname.match(/^\/game\/ai\/([^/]+)$/i);
  return match ? match[1] : null;
}

function showLobby(message = "", isError = false) {
  appMode = "lobby";
  cleanupOnlineConnection();
  aiThinking = false;
  clockStarted = false;
  lastClockTick = Date.now();
  lobbyEl.classList.remove("hidden");
  gameAppEl.classList.add("hidden");
  lobbyResultEl.textContent = message;
  lobbyResultEl.classList.toggle("error", isError);
}

function showGame(mode) {
  appMode = mode;
  lobbyEl.classList.add("hidden");
  gameAppEl.classList.remove("hidden");
  configureActionButtons();
}

function navigateTo(path) {
  if (window.location.pathname !== path) {
    history.pushState({}, "", path);
  }
}

function configureActionButtons() {
  if (appMode === "online") {
    newGameButton.innerHTML = '<span aria-hidden="true">⧉</span><strong>Copy Link</strong>';
    undoButton.innerHTML = '<span aria-hidden="true">↩</span><strong>Leave</strong>';
    redoButton.innerHTML = '<span aria-hidden="true">＋</span><strong>New Local</strong>';
    saveButton.classList.add("hidden");
    loadButton.classList.add("hidden");
    return;
  }
  if (appMode === "ai") {
    newGameButton.innerHTML = '<span aria-hidden="true">＋</span><strong>New AI</strong>';
    undoButton.innerHTML = '<span aria-hidden="true">↩</span><strong>Back</strong>';
    redoButton.innerHTML = '<span aria-hidden="true">＋</span><strong>New Local</strong>';
    saveButton.classList.add("hidden");
    loadButton.classList.add("hidden");
    return;
  }
  newGameButton.innerHTML = '<span aria-hidden="true">＋</span><strong>New</strong>';
  undoButton.innerHTML = '<span aria-hidden="true">↶</span><strong>Undo</strong>';
  redoButton.innerHTML = '<span aria-hidden="true">↷</span><strong>Redo</strong>';
  saveButton.innerHTML = '<span aria-hidden="true">⇩</span><strong>Save</strong>';
  loadButton.innerHTML = '<span aria-hidden="true">▰</span><strong>Load</strong>';
  saveButton.classList.remove("hidden");
  loadButton.classList.remove("hidden");
}

function render() {
  updateClockFromNow();
  boardEl.innerHTML = "";
  boardEl.style.setProperty("--board-columns", String(visibleFileCount()));
  boardEl.closest(".board-shell").style.setProperty("--board-columns", String(visibleFileCount()));
  boardEl.closest(".board-shell").classList.toggle("wide-view", boardView === "wide");
  boardEl.closest(".board-shell").classList.toggle("board-flipped", isBoardFlipped());
  boardViewToggle.textContent = boardView === "wide" ? "View: 8x8" : "View: 15x8";
  boardViewToggle.dataset.view = boardView;
  renderFileLabels();
  renderRankLabels();
  const legalMoves = state ? state.legal_moves : [];
  const latestMove = latestMoveEntry();
  const latestFrom = latestMove ? entryFromSquare(latestMove) : null;
  const latestTo = latestMove ? entryToSquare(latestMove) : null;
  const selectedMoves = selected
    ? legalMoves.filter((move) => move.slice(0, 2) === selected)
    : [];
  const targets = new Map(selectedMoves.map((move) => [move.slice(2, 4), move]));

  for (const rank of visibleRanks()) {
    for (let displayFile = 0; displayFile < visibleFileCount(); displayFile += 1) {
      const file = displayFileAt(displayFile);
      const square = squareName(file, rank);
      const button = document.createElement("button");
      button.type = "button";
      button.className = `square ${(file + rank) % 2 === 0 ? "dark" : "light"}`;
      button.dataset.square = square;
      button.setAttribute("role", "gridcell");
      button.setAttribute("aria-label", displaySquare(square));

      if (square === selected) {
        button.classList.add("selected");
      }
      if (square === latestFrom) {
        button.classList.add("last-move-from");
      }
      if (square === latestTo) {
        button.classList.add("last-move-to");
      }
      if (targets.has(square)) {
        const hasPiece = Boolean(state.pieces[square]);
        button.classList.add(hasPiece ? "capture" : "target");
        if (Math.abs(fileIndex(selected) - fileIndex(square)) > 4) {
          button.classList.add("wrap-target");
        }
      }

      const piece = state ? state.pieces[square] : null;
      if (piece) {
        const pieceEl = document.createElement("span");
        pieceEl.className = "piece";
        pieceEl.textContent = pieceSymbols[piece];
        button.append(pieceEl);
      }

      button.addEventListener("pointerdown", (event) => handleSquarePointerDown(event, square));
      button.addEventListener("click", () => {
        if (suppressNextClick) {
          suppressNextClick = false;
          return;
        }
        handleSquareClick(square);
      });
      boardEl.append(button);
    }
  }

  renderStatus();
  renderPlayerState();
  renderClocks();
  renderCapturedPieces();
  renderHistory();
}

function renderFileLabels() {
  const labels = rotatedFiles();
  [filesTopEl, filesBottomEl].forEach((container) => {
    container.innerHTML = "";
    labels.forEach((file) => {
      const span = document.createElement("span");
      span.textContent = displayFile(file);
      container.append(span);
    });
  });
  leftFileLabel.textContent = displayFile(files[leftFileIndex]);
}

function renderRankLabels() {
  const ranks = visibleRanks();
  rankLabelEls.forEach((container) => {
    container.innerHTML = "";
    ranks.forEach((rank) => {
      const span = document.createElement("span");
      span.textContent = String(rank);
      container.append(span);
    });
  });
}

function renderStatus() {
  if (!state) {
    statusEl.textContent = appMode === "online" ? "Connecting" : "Starting";
    return;
  }
  if (appMode === "online") {
    if (roomData?.status === "waiting") {
      statusEl.textContent = `Waiting for opponent · Room ${currentRoomId}`;
      return;
    }
    if (state.result.status === "ongoing") {
      const turnText = state.turn === playerColor ? "Your move" : "Opponent to move";
      statusEl.textContent = `${turnText} · Room ${currentRoomId}`;
      return;
    }
  }
  if (appMode === "ai" && state.result.status === "ongoing") {
    if (aiThinking) {
      statusEl.textContent = "AI thinking";
      return;
    }
    if (state.turn === playerColor) {
      const reply = aiLastMove ? ` · AI played ${displayMove(aiLastMove)}` : "";
      statusEl.textContent = `Your move${reply}`;
      return;
    }
    statusEl.textContent = "AI thinking";
    return;
  }
  if (!state) {
    statusEl.textContent = "Starting";
    return;
  }
  if (state.result.status === "checkmate") {
    statusEl.textContent = `Checkmate. ${state.result.winner} wins.`;
    return;
  }
  if (state.result.status === "stalemate") {
    statusEl.textContent = "Stalemate.";
    return;
  }
  statusEl.textContent = state.is_check ? `${state.turn} in check` : `${state.turn} to move`;
}

function renderPlayerState() {
  const activeColor = state?.result.status === "ongoing" ? state.turn : null;
  whitePlayerEl.classList.toggle("active", activeColor === "white");
  blackPlayerEl.classList.toggle("active", activeColor === "black");
  whitePlayerEl.setAttribute("aria-current", activeColor === "white" ? "true" : "false");
  blackPlayerEl.setAttribute("aria-current", activeColor === "black" ? "true" : "false");
  renderPlayerCard("white");
  renderPlayerCard("black");
}

function renderPlayerCard(color) {
  const card = color === "white" ? whitePlayerEl : blackPlayerEl;
  const player = appMode === "online" ? roomData?.players?.[color] : null;
  const isAIPlayer = appMode === "ai" && color === aiColor;
  const isHumanAIPlayer = appMode === "ai" && color === playerColor;
  const nickname = isAIPlayer
    ? "Rolling AI"
    : player?.nickname || (isHumanAIPlayer ? displayNickname() : color === "white" ? "Atlas" : "Nocturne");
  const side = card.querySelector(".player-side");
  const name = card.querySelector(".player-identity strong");
  const meta = card.querySelector(".player-identity small");
  const avatar = card.querySelector(".avatar");
  side.textContent = `${displayFile(color[0])}${color.slice(1)}${player?.is_you || isHumanAIPlayer ? " · You" : ""}`;
  name.textContent = nickname;
  meta.textContent = playerMetaText(player, isAIPlayer, isHumanAIPlayer);
  avatar.textContent = isAIPlayer ? "AI" : nickname.trim()[0]?.toUpperCase() || (color === "white" ? "A" : "N");
}

function playerMetaText(player, isAIPlayer, isHumanAIPlayer) {
  if (appMode === "online") {
    return player?.connected ? "Connected" : "Disconnected";
  }
  if (isAIPlayer) {
    const modelNote = aiDifficulty === "experimental" ? ` · ${aiModelStatus}` : "";
    return `${displayFile(aiDifficulty[0])}${aiDifficulty.slice(1)}${modelNote}`;
  }
  if (isHumanAIPlayer) {
    return "Human";
  }
  return "Rating 1500";
}

function renderClocks() {
  whiteClockEl.textContent = formatClock(clocks.white);
  blackClockEl.textContent = formatClock(clocks.black);
  whiteClockEl.dateTime = `PT${Math.max(0, Math.round(clocks.white))}S`;
  blackClockEl.dateTime = `PT${Math.max(0, Math.round(clocks.black))}S`;
}

function formatClock(seconds) {
  const bounded = Math.max(0, Math.floor(seconds));
  const minutes = String(Math.floor(bounded / 60)).padStart(2, "0");
  const remainder = String(bounded % 60).padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function resetClocks() {
  clocks = { white: initialClockSeconds, black: initialClockSeconds };
  clockStarted = false;
  lastClockTick = Date.now();
}

function updateClockFromNow() {
  if (!clockStarted || !state || state.result.status !== "ongoing") {
    lastClockTick = Date.now();
    return;
  }
  const now = Date.now();
  const elapsed = Math.floor((now - lastClockTick) / 1000);
  if (elapsed <= 0) {
    return;
  }
  clocks[state.turn] = Math.max(0, clocks[state.turn] - elapsed);
  lastClockTick += elapsed * 1000;
}

function whiteFirstMoveHasLanded(gameState = state) {
  return Array.isArray(gameState?.history) && gameState.history.length > 0;
}

function updateClockGateFromState(gameState = state) {
  const shouldRun = whiteFirstMoveHasLanded(gameState);
  if (clockStarted !== shouldRun) {
    clockStarted = shouldRun;
    lastClockTick = Date.now();
  }
}

function savedClocks(payload) {
  if (!payload || typeof payload !== "object" || !payload.clocks) {
    return { white: initialClockSeconds, black: initialClockSeconds };
  }
  const white = Number(payload.clocks.white);
  const black = Number(payload.clocks.black);
  return {
    white: Number.isFinite(white) ? Math.max(0, white) : initialClockSeconds,
    black: Number.isFinite(black) ? Math.max(0, black) : initialClockSeconds,
  };
}

function savedClockStarted(payload, gameState) {
  if (typeof payload?.clockStarted === "boolean") {
    return payload.clockStarted && whiteFirstMoveHasLanded(gameState);
  }
  return whiteFirstMoveHasLanded(gameState);
}

function renderHistory() {
  historyEl.innerHTML = "";
  if (!state) {
    return;
  }
  historyEntries().forEach((entry) => {
    const item = document.createElement("li");
    item.textContent = formatHistoryEntry(entry);
    historyEl.append(item);
  });
}

function historyEntries() {
  if (Array.isArray(state.history_details) && state.history_details.length > 0) {
    return state.history_details;
  }
  return state.history.map((move) => ({ move }));
}

function latestMoveEntry() {
  if (!state) {
    return null;
  }
  const entries = historyEntries();
  return entries.length > 0 ? entries[entries.length - 1] : null;
}

function entryFromSquare(entry) {
  return entry.from || entry.move?.slice(0, 2) || null;
}

function entryToSquare(entry) {
  return entry.to || entry.move?.slice(2, 4) || null;
}

function movingPieceSymbol(entry) {
  if (entry.piece_symbol && pieceSymbols[entry.piece_symbol]) {
    return pieceSymbols[entry.piece_symbol];
  }
  return "";
}

function formatHistoryEntry(entry) {
  const movingPiece = movingPieceSymbol(entry);
  const prefix = movingPiece ? `${movingPiece} ` : "";
  if (!entry.capture) {
    return `${prefix}${displayMove(entry.move)}`;
  }
  const promotion = (entry.promotion || "").toUpperCase();
  const captureSymbol = pieceSymbols[entry.capture_symbol] || pieceSymbols[entry.capture] || entry.capture;
  const enPassant = entry.capture_kind === "en_passant" ? " e.p." : "";
  return `${prefix}${displaySquare(entryFromSquare(entry))}x${displaySquare(entryToSquare(entry))}${promotion}${enPassant} ${captureSymbol}`;
}

function renderCapturedPieces() {
  if (!state) {
    whiteCapturedEl.textContent = "-";
    blackCapturedEl.textContent = "-";
    return;
  }
  const captured = capturedPiecesFromBoard(state.pieces);
  whiteCapturedEl.textContent = renderPieceList(captured.byWhite, "black") || "-";
  blackCapturedEl.textContent = renderPieceList(captured.byBlack, "white") || "-";
}

function capturedPiecesFromBoard(pieces) {
  const current = {
    white: { k: 0, q: 0, r: 0, b: 0, n: 0, p: 0 },
    black: { k: 0, q: 0, r: 0, b: 0, n: 0, p: 0 },
  };
  Object.values(pieces).forEach((piece) => {
    const color = piece === piece.toUpperCase() ? "white" : "black";
    current[color][piece.toLowerCase()] += 1;
  });

  return {
    byWhite: missingMaterial("black", current.black),
    byBlack: missingMaterial("white", current.white),
  };
}

function missingMaterial(color, currentCounts) {
  const missing = {};
  pieceOrder.forEach((type) => {
    missing[type] = Math.max(0, initialMaterial[color][type] - currentCounts[type]);
  });

  let livePromotions = 0;
  ["q", "r", "b", "n"].forEach((type) => {
    livePromotions += Math.max(0, currentCounts[type] - initialMaterial[color][type]);
  });
  missing.p = Math.max(0, missing.p - livePromotions);
  return missing;
}

function renderPieceList(counts, color) {
  return pieceOrder
    .flatMap((type) => {
      const symbol = color === "white" ? type.toUpperCase() : type;
      return Array.from({ length: counts[type] }, () => pieceSymbols[symbol]);
    })
    .join("");
}

function handleSquareClick(square) {
  if (!isGameInteractive()) {
    return;
  }
  const piece = state.pieces[square];
  if (!selected) {
    if (piece && isOwnPiece(piece)) {
      selected = square;
      render();
    }
    return;
  }

  if (attemptMove(selected, square)) {
    return;
  }

  if (piece && isOwnPiece(piece)) {
    selected = square;
  } else {
    selected = null;
  }
  render();
}

function handleSquarePointerDown(event, square) {
  if (!isGameInteractive()) {
    return;
  }
  if (event.button !== undefined && event.button !== 0) {
    return;
  }
  const piece = state.pieces[square];
  if (!piece || !isOwnPiece(piece)) {
    return;
  }
  dragState = {
    pointerId: event.pointerId,
    from: square,
    piece,
    startX: event.clientX,
    startY: event.clientY,
    dragging: false,
    ghost: null,
  };
}

function handleGlobalPointerDown(event) {
  if (dragState?.dragging && event.button === 2) {
    event.preventDefault();
    suppressNextClick = true;
    cancelDragInteraction();
  }
}

function handlePointerMove(event) {
  if (!dragState || event.pointerId !== dragState.pointerId) {
    return;
  }
  const dx = event.clientX - dragState.startX;
  const dy = event.clientY - dragState.startY;
  if (!dragState.dragging && Math.hypot(dx, dy) >= dragThreshold) {
    startDrag(event);
  }
  if (dragState.dragging) {
    event.preventDefault();
    updateDragGhost(event);
  }
}

function handlePointerUp(event) {
  if (!dragState || event.pointerId !== dragState.pointerId) {
    return;
  }
  if (!dragState.dragging) {
    dragState = null;
    return;
  }
  event.preventDefault();
  const source = dragState.from;
  const target = squareFromPoint(event.clientX, event.clientY);
  cleanupDrag();
  if (target && attemptMove(source, target)) {
    return;
  }
  selected = null;
  render();
}

function handlePointerCancel(event) {
  if (!dragState || event.pointerId !== dragState.pointerId) {
    return;
  }
  cancelDragInteraction();
}

function handleContextMenu(event) {
  if (!dragState?.dragging) {
    return;
  }
  event.preventDefault();
  suppressNextClick = true;
  cancelDragInteraction();
}

function handlePageInterruption() {
  if (dragState?.dragging) {
    cancelDragInteraction();
  }
}

function startDrag(event) {
  dragState.dragging = true;
  suppressNextClick = true;
  selected = dragState.from;
  render();
  const ghost = document.createElement("div");
  ghost.className = "drag-ghost";
  ghost.textContent = pieceSymbols[dragState.piece];
  const renderedPiece = boardEl.querySelector(".square.selected .piece");
  if (renderedPiece) {
    ghost.style.fontSize = getComputedStyle(renderedPiece).fontSize;
  }
  document.body.append(ghost);
  dragState.ghost = ghost;
  boardEl.classList.add("dragging");
  updateDragGhost(event);
}

function updateDragGhost(event) {
  if (!dragState?.ghost) {
    return;
  }
  dragState.ghost.style.left = `${event.clientX}px`;
  dragState.ghost.style.top = `${event.clientY}px`;
}

function cleanupDrag() {
  if (dragState?.ghost) {
    dragState.ghost.remove();
  }
  boardEl.classList.remove("dragging");
  dragState = null;
}

function cancelDragInteraction() {
  cleanupDrag();
  selected = null;
  render();
}

function squareFromPoint(clientX, clientY) {
  const element = document.elementFromPoint(clientX, clientY);
  return element?.closest(".square")?.dataset.square || null;
}

function attemptMove(from, to) {
  const matchingMoves = state.legal_moves.filter(
    (move) => move.slice(0, 2) === from && move.slice(2, 4) === to,
  );
  if (matchingMoves.length === 0) {
    return false;
  }
  const promotionMoves = matchingMoves.filter((move) => move.length === 5);
  if (promotionMoves.length > 0) {
    pendingPromotion = { from, to };
    selected = null;
    render();
    showPromotion();
    return true;
  }
  submitMove(matchingMoves[0]);
  return true;
}

function isGameInteractive() {
  if (!state || state.result.status !== "ongoing") {
    return false;
  }
  if (appMode === "ai") {
    return Boolean(!aiThinking && state.turn === playerColor);
  }
  if (appMode !== "online") {
    return true;
  }
  return Boolean(roomData?.status === "active" && state.turn === playerColor && roomSocket?.readyState === WebSocket.OPEN);
}

function isOwnPiece(piece) {
  const color = appMode === "online" || appMode === "ai" ? playerColor : state.turn;
  return color === "white" ? piece === piece.toUpperCase() : piece === piece.toLowerCase();
}

async function newGame() {
  const response = await fetch("/api/games", { method: "POST" });
  const payload = await response.json();
  gameId = payload.game_id;
  state = payload.state;
  selected = null;
  resetClocks();
  updateClockGateFromState();
  render();
}

async function submitMove(move) {
  if (appMode === "online") {
    submitOnlineMove(move);
    return;
  }
  if (appMode === "ai") {
    submitAIMove(move);
    return;
  }
  updateClockFromNow();
  const response = await fetch(`/api/games/${gameId}/moves`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ move }),
  });
  const payload = await response.json();
  if (!response.ok) {
    statusEl.textContent = payload.detail || payload.error || "Illegal move";
    return;
  }
  state = payload.state;
  selected = null;
  updateClockGateFromState();
  lastClockTick = Date.now();
  render();
}

async function submitAIMove(move) {
  if (!aiGameId || aiThinking) {
    return;
  }
  updateClockFromNow();
  const playerResponse = await fetch(`/api/ai/games/${aiGameId}/player-moves`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ move }),
  });
  const playerPayload = await playerResponse.json();
  if (!playerResponse.ok) {
    aiThinking = false;
    statusEl.textContent = playerPayload.detail || playerPayload.error || "AI move failed";
    return;
  }
  applyAISession(playerPayload);
  aiThinking = playerPayload.state.result.status === "ongoing";
  lastClockTick = Date.now();
  render();
  if (!aiThinking) {
    return;
  }

  const response = await fetch(`/api/ai/games/${aiGameId}/ai-move`, { method: "POST" });
  const payload = await response.json();
  aiThinking = false;
  if (!response.ok) {
    statusEl.textContent = payload.detail || payload.error || "AI move failed";
    return;
  }
  applyAISession(payload);
  lastClockTick = Date.now();
  render();
}

async function undo() {
  if (!gameId) {
    return;
  }
  updateClockFromNow();
  const response = await fetch(`/api/games/${gameId}/undo`, { method: "POST" });
  const payload = await response.json();
  if (response.ok) {
    state = payload.state;
    selected = null;
    updateClockGateFromState();
    lastClockTick = Date.now();
    render();
  }
}

async function redo() {
  if (!gameId) {
    return;
  }
  updateClockFromNow();
  const response = await fetch(`/api/games/${gameId}/redo`, { method: "POST" });
  const payload = await response.json();
  if (response.ok) {
    state = payload.state;
    selected = null;
    updateClockGateFromState();
    lastClockTick = Date.now();
    render();
  }
}

async function saveGame() {
  if (!gameId) {
    return;
  }
  updateClockFromNow();
  const response = await fetch(`/api/games/${gameId}/export`);
  const payload = await response.json();
  if (response.ok) {
    localStorage.setItem(storageKey, JSON.stringify({ ...payload, clocks, clockStarted }));
    statusEl.textContent = "Saved";
  }
}

async function loadGame() {
  const saved = localStorage.getItem(storageKey);
  if (!saved) {
    statusEl.textContent = "No saved game";
    return;
  }
  let savedPayload = null;
  try {
    savedPayload = JSON.parse(saved);
  } catch {
    statusEl.textContent = "Load failed";
    return;
  }
  const response = await fetch("/api/games/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: savedPayload.state }),
  });
  const payload = await response.json();
  if (!response.ok) {
    statusEl.textContent = payload.error || "Load failed";
    return;
  }
  gameId = payload.game_id;
  state = payload.state;
  selected = null;
  clocks = savedClocks(savedPayload);
  clockStarted = savedClockStarted(savedPayload, state);
  lastClockTick = Date.now();
  render();
}

function applyAISession(payload) {
  aiGameId = payload.game_id;
  gameId = null;
  state = payload.state;
  playerColor = payload.player_color;
  aiColor = payload.ai_color;
  aiDifficulty = payload.difficulty;
  aiLastMove = payload.last_ai_move;
  aiModelStatus = payload.model_status || "not_used";
  selected = null;
  pendingPromotion = null;
  updateClockGateFromState();
}

async function startAIGame(pushRoute = true) {
  cleanupOnlineConnection();
  currentRoomId = null;
  playerToken = null;
  roomData = null;
  roomVersion = 0;
  aiThinking = false;
  const response = await fetch("/api/ai/games", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      player_color: aiPlayerColorSelect.value,
      difficulty: aiDifficultySelect.value,
    }),
  });
  const payload = await response.json();
  if (!response.ok) {
    showLobby(payload.detail || "AI game failed to start.", true);
    return;
  }
  resetClocks();
  currentNickname();
  applyAISession(payload);
  lastClockTick = Date.now();
  showGame("ai");
  if (pushRoute) {
    navigateTo(`/game/ai/${aiGameId}`);
  }
  render();
}

async function loadAIGame(id) {
  cleanupOnlineConnection();
  currentRoomId = null;
  playerToken = null;
  roomData = null;
  roomVersion = 0;
  aiThinking = false;
  const response = await fetch(`/api/ai/games/${id}`);
  const payload = await response.json();
  if (!response.ok) {
    showLobby(payload.detail || "AI game not found.", true);
    return;
  }
  resetClocks();
  applyAISession(payload);
  aiPlayerColorSelect.value = playerColor;
  aiDifficultySelect.value = aiDifficulty;
  lastClockTick = Date.now();
  showGame("ai");
  render();
}

async function startLocalGame(pushRoute = true) {
  cleanupOnlineConnection();
  currentRoomId = null;
  playerToken = null;
  playerColor = null;
  roomData = null;
  aiGameId = null;
  aiColor = null;
  aiLastMove = null;
  aiThinking = false;
  resetClocks();
  showGame("local");
  if (pushRoute) {
    navigateTo("/game/local");
  }
  await newGame();
}

async function createOnlineRoom() {
  const nickname = currentNickname();
  const response = await fetch("/api/rooms", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname }),
  });
  const payload = await response.json();
  if (!response.ok) {
    showLobby(payload.detail || "Room creation failed", true);
    return;
  }
  saveRoomIdentity(payload.room_id, {
    token: payload.player_token,
    nickname,
    color: payload.assigned_color,
  });
  const url = roomUrl(payload.room_id);
  lobbyResultEl.innerHTML = `Room ${payload.room_id} created. <a href="${url}">${url}</a>`;
  navigateTo(`/room/${payload.room_id}`);
  startOnlineRoom(payload.room_id);
}

async function joinOnlineRoom(roomId = roomCodeInput.value) {
  const normalizedRoomId = roomId.trim().toUpperCase();
  if (!normalizedRoomId) {
    showLobby("Enter a room code.", true);
    return;
  }
  const nickname = currentNickname();
  const existing = savedRoomIdentity(normalizedRoomId);
  const response = await fetch(`/api/rooms/${normalizedRoomId}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname, player_token: existing?.token }),
  });
  const payload = await response.json();
  if (!response.ok) {
    showLobby(payload.detail || "Could not join room.", true);
    return;
  }
  saveRoomIdentity(normalizedRoomId, {
    token: payload.player_token,
    nickname,
    color: payload.assigned_color,
  });
  navigateTo(`/room/${normalizedRoomId}`);
  startOnlineRoom(normalizedRoomId);
}

function startOnlineRoom(roomId) {
  const normalizedRoomId = roomId.toUpperCase();
  const identity = savedRoomIdentity(normalizedRoomId);
  if (!identity?.token) {
    roomCodeInput.value = normalizedRoomId;
    showLobby(`Enter a nickname to join room ${normalizedRoomId}.`);
    return;
  }
  cleanupOnlineConnection();
  currentRoomId = normalizedRoomId;
  playerToken = identity.token;
  playerColor = identity.color || null;
  roomData = null;
  aiGameId = null;
  aiColor = null;
  aiLastMove = null;
  aiThinking = false;
  state = null;
  selected = null;
  resetClocks();
  showGame("online");
  connectRoomSocket();
  render();
}

function connectRoomSocket() {
  if (!currentRoomId || !playerToken) {
    return;
  }
  clearTimeout(reconnectTimer);
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  roomSocket = new WebSocket(`${protocol}://${window.location.host}/ws/rooms/${currentRoomId}`);
  statusEl.textContent = "Connecting";
  roomSocket.addEventListener("open", () => {
    roomSocket.send(JSON.stringify({
      type: "join",
      room_id: currentRoomId,
      token: playerToken,
      nickname: currentNickname(),
    }));
  });
  roomSocket.addEventListener("message", (event) => {
    handleRoomSocketMessage(JSON.parse(event.data));
  });
  roomSocket.addEventListener("close", () => {
    if (appMode !== "online") {
      return;
    }
    statusEl.textContent = "Reconnecting";
    reconnectTimer = setTimeout(connectRoomSocket, 1200);
  });
}

function handleRoomSocketMessage(message) {
  if (message.type === "room_state") {
    updateClockFromNow();
    roomData = message.room;
    state = roomData.state;
    roomVersion = roomData.version;
    playerColor = roomData.viewer_color || playerColor;
    const identity = savedRoomIdentity(currentRoomId) || {};
    saveRoomIdentity(currentRoomId, {
      ...identity,
      token: playerToken,
      color: playerColor,
      nickname: currentNickname(),
    });
    updateClockGateFromState();
    lastClockTick = Date.now();
    render();
    return;
  }
  if (message.type === "move_rejected" || message.type === "error") {
    statusEl.textContent = message.error || "Online move failed";
  }
}

function submitOnlineMove(move) {
  if (!roomSocket || roomSocket.readyState !== WebSocket.OPEN) {
    statusEl.textContent = "Reconnecting";
    return;
  }
  roomSocket.send(JSON.stringify({ type: "move", move, version: roomVersion }));
}

function cleanupOnlineConnection() {
  clearTimeout(reconnectTimer);
  reconnectTimer = null;
  if (roomSocket) {
    const socket = roomSocket;
    roomSocket = null;
    socket.close();
  }
}

function roomUrl(roomId) {
  return `${window.location.origin}/room/${roomId}`;
}

async function copyRoomLink() {
  if (!currentRoomId) {
    return;
  }
  const url = roomUrl(currentRoomId);
  try {
    await navigator.clipboard.writeText(url);
    statusEl.textContent = `Copied ${currentRoomId}`;
  } catch {
    statusEl.textContent = url;
  }
}

function leaveRoom() {
  cleanupOnlineConnection();
  showLobby("Left room.");
  navigateTo("/");
}

function returnToLobby(message = "") {
  cleanupOnlineConnection();
  showLobby(message);
  navigateTo("/");
}

function handleNewAction() {
  if (appMode === "online") {
    copyRoomLink();
    return;
  }
  if (appMode === "ai") {
    startAIGame();
    return;
  }
  newGame();
}

function handleUndoAction() {
  if (appMode === "online") {
    leaveRoom();
    return;
  }
  if (appMode === "ai") {
    returnToLobby();
    return;
  }
  undo();
}

function handleRedoAction() {
  if (appMode === "online") {
    startLocalGame();
    return;
  }
  if (appMode === "ai") {
    startLocalGame();
    return;
  }
  redo();
}

function initializeRoute() {
  nicknameInput.value = localStorage.getItem(nicknameStorageKey) || "";
  const roomId = roomIdFromPath();
  const routeAIGameId = aiGameIdFromPath();
  if (window.location.pathname === "/game/local") {
    startLocalGame(false);
    return;
  }
  if (routeAIGameId) {
    loadAIGame(routeAIGameId);
    return;
  }
  if (roomId) {
    startOnlineRoom(roomId);
    return;
  }
  showLobby();
}

function showPromotion() {
  promotionEl.classList.remove("hidden");
}

function hidePromotion() {
  promotionEl.classList.add("hidden");
}

promotionEl.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-piece]");
  if (!button || !pendingPromotion) {
    return;
  }
  const move = `${pendingPromotion.from}${pendingPromotion.to}${button.dataset.piece}`;
  pendingPromotion = null;
  hidePromotion();
  submitMove(move);
});

localGameButton.addEventListener("click", () => startLocalGame());
createRoomButton.addEventListener("click", createOnlineRoom);
startAIButton.addEventListener("click", () => startAIGame());
homeButton.addEventListener("click", () => returnToLobby());
joinRoomForm.addEventListener("submit", (event) => {
  event.preventDefault();
  joinOnlineRoom();
});
newGameButton.addEventListener("click", handleNewAction);
undoButton.addEventListener("click", handleUndoAction);
redoButton.addEventListener("click", handleRedoAction);
saveButton.addEventListener("click", () => {
  if (appMode === "local") {
    saveGame();
  }
});
loadButton.addEventListener("click", () => {
  if (appMode === "local") {
    loadGame();
  }
});
leftFileInput.addEventListener("input", () => {
  leftFileIndex = Number(leftFileInput.value);
  render();
});
function rotateFiles(delta) {
  leftFileIndex = (leftFileIndex + delta + files.length) % files.length;
  leftFileInput.value = String(leftFileIndex);
  render();
}

rotatePrevButton.addEventListener("click", () => rotateFiles(-1));
rotateNextButton.addEventListener("click", () => rotateFiles(1));
boardViewToggle.addEventListener("click", () => {
  boardView = boardView === "wide" ? "standard" : "wide";
  render();
});
document.addEventListener("pointerdown", handleGlobalPointerDown, true);
document.addEventListener("pointermove", handlePointerMove);
document.addEventListener("pointerup", handlePointerUp);
document.addEventListener("pointercancel", handlePointerCancel);
document.addEventListener("contextmenu", handleContextMenu);
window.addEventListener("blur", handlePageInterruption);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    handlePageInterruption();
  }
});
window.addEventListener("popstate", initializeRoute);
setInterval(() => {
  updateClockFromNow();
  renderClocks();
}, 1000);

initializeRoute();
