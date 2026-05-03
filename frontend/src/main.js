const boardEl = document.querySelector("#board");
const statusEl = document.querySelector("#status");
const historyEl = document.querySelector("#history");
const newGameButton = document.querySelector("#new-game");
const undoButton = document.querySelector("#undo");
const redoButton = document.querySelector("#redo");
const saveButton = document.querySelector("#save");
const loadButton = document.querySelector("#load");
const whiteCapturedEl = document.querySelector("#white-captured");
const blackCapturedEl = document.querySelector("#black-captured");
const promotionEl = document.querySelector("#promotion");
const storageKey = "rolling-chess-save";

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

function squareName(file, rank) {
  return `${files[file]}${rank}`;
}

function fileIndex(square) {
  return files.indexOf(square[0]);
}

function render() {
  boardEl.innerHTML = "";
  const legalMoves = state ? state.legal_moves : [];
  const selectedMoves = selected
    ? legalMoves.filter((move) => move.slice(0, 2) === selected)
    : [];
  const targets = new Map(selectedMoves.map((move) => [move.slice(2, 4), move]));

  for (let rank = 8; rank >= 1; rank -= 1) {
    for (let file = 0; file < 8; file += 1) {
      const square = squareName(file, rank);
      const button = document.createElement("button");
      button.type = "button";
      button.className = `square ${(file + rank) % 2 === 0 ? "dark" : "light"}`;
      button.dataset.square = square;
      button.setAttribute("role", "gridcell");
      button.setAttribute("aria-label", square);

      if (square === selected) {
        button.classList.add("selected");
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

      button.addEventListener("click", () => handleSquareClick(square));
      boardEl.append(button);
    }
  }

  renderStatus();
  renderCapturedPieces();
  renderHistory();
}

function renderStatus() {
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

function formatHistoryEntry(entry) {
  if (!entry.capture) {
    return entry.move;
  }
  const promotion = entry.promotion || "";
  const captureSymbol = pieceSymbols[entry.capture_symbol] || pieceSymbols[entry.capture] || entry.capture;
  const enPassant = entry.capture_kind === "en_passant" ? " e.p." : "";
  return `${entry.from}x${entry.to}${promotion}${enPassant} ${captureSymbol}`;
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
  if (!state || state.result.status !== "ongoing") {
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

  const matchingMoves = state.legal_moves.filter(
    (move) => move.slice(0, 2) === selected && move.slice(2, 4) === square,
  );
  if (matchingMoves.length > 0) {
    const promotionMoves = matchingMoves.filter((move) => move.length === 5);
    if (promotionMoves.length > 0) {
      pendingPromotion = { from: selected, to: square };
      showPromotion();
      return;
    }
    submitMove(matchingMoves[0]);
    return;
  }

  if (piece && isOwnPiece(piece)) {
    selected = square;
  } else {
    selected = null;
  }
  render();
}

function isOwnPiece(piece) {
  return state.turn === "white" ? piece === piece.toUpperCase() : piece === piece.toLowerCase();
}

async function newGame() {
  const response = await fetch("/api/games", { method: "POST" });
  const payload = await response.json();
  gameId = payload.game_id;
  state = payload.state;
  selected = null;
  render();
}

async function submitMove(move) {
  const response = await fetch(`/api/games/${gameId}/moves`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ move }),
  });
  const payload = await response.json();
  if (!response.ok) {
    statusEl.textContent = payload.error || "Illegal move";
    return;
  }
  state = payload.state;
  selected = null;
  render();
}

async function undo() {
  if (!gameId) {
    return;
  }
  const response = await fetch(`/api/games/${gameId}/undo`, { method: "POST" });
  const payload = await response.json();
  if (response.ok) {
    state = payload.state;
    selected = null;
    render();
  }
}

async function redo() {
  if (!gameId) {
    return;
  }
  const response = await fetch(`/api/games/${gameId}/redo`, { method: "POST" });
  const payload = await response.json();
  if (response.ok) {
    state = payload.state;
    selected = null;
    render();
  }
}

async function saveGame() {
  if (!gameId) {
    return;
  }
  const response = await fetch(`/api/games/${gameId}/export`);
  const payload = await response.json();
  if (response.ok) {
    localStorage.setItem(storageKey, JSON.stringify(payload));
    statusEl.textContent = "Saved";
  }
}

async function loadGame() {
  const saved = localStorage.getItem(storageKey);
  if (!saved) {
    statusEl.textContent = "No saved game";
    return;
  }
  const response = await fetch("/api/games/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: saved,
  });
  const payload = await response.json();
  if (!response.ok) {
    statusEl.textContent = payload.error || "Load failed";
    return;
  }
  gameId = payload.game_id;
  state = payload.state;
  selected = null;
  render();
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

newGameButton.addEventListener("click", newGame);
undoButton.addEventListener("click", undo);
redoButton.addEventListener("click", redo);
saveButton.addEventListener("click", saveGame);
loadButton.addEventListener("click", loadGame);

newGame();
